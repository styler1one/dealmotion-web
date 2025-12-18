"""
Exa Comprehensive Research Service - State-of-the-art B2B prospect research.

This service mirrors the Gemini-first architecture but uses Exa's APIs:
- 30 PARALLEL search calls for maximum coverage
- Each call focuses on ONE specific research area
- Uses Exa's specialized capabilities (category filters, domain filters, date filters)
- Output: Comprehensive structured raw data for Claude to analyze

Architecture:
- COMPANY (4 calls): identity, business model, products, financials
- PEOPLE (6 calls): CEO, C-suite, senior leadership, board, changes, founder story
- MARKET (5 calls): news, partnerships, hiring, tech stack, competition
- DEEP INSIGHTS (7 calls): reviews, events, awards, media, customers, challenges, certifications
- STRATEGIC (6 calls): key accounts, risks, roadmap, ESG, patents, vendors
- LOCAL (2 calls): country-specific media and rankings

Features:
- International support with country-specific business media sources
- Specialized category filters (people, company, news)
- Domain filtering for quality sources (Crunchbase, G2, Glassdoor, etc.)
- Date filtering for recent news
- Answer API for specific factual queries
"""

import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# Local Business Sources - International Support
# =============================================================================

LOCAL_BUSINESS_SOURCES = {
    # Netherlands
    "nl": {
        "name": "Dutch Business Media",
        "domains": ["fd.nl", "mt.nl", "sprout.nl", "bnr.nl", "emerce.nl", "quotenet.nl", "computable.nl"],
        "rankings": "FD Gazellen MT500 Deloitte Fast50 Best Managed Companies EY Entrepreneur",
        "language": "Dutch"
    },
    
    # Germany
    "de": {
        "name": "German Business Media",
        "domains": ["handelsblatt.com", "manager-magazin.de", "wiwo.de", "gruenderszene.de", "t3n.de"],
        "rankings": "Top 500 Focus Growth Champions Technology Fast 50",
        "language": "German"
    },
    
    # United Kingdom
    "uk": {
        "name": "UK Business Media",
        "domains": ["ft.com", "cityam.com", "thisismoney.co.uk", "uktech.news", "sifted.eu"],
        "rankings": "Sunday Times Fast Track Tech Track 100 Deloitte Fast 50 UK",
        "language": "English"
    },
    
    # United States
    "us": {
        "name": "US Business Media",
        "domains": ["wsj.com", "forbes.com", "fortune.com", "businessinsider.com", "techcrunch.com", "venturebeat.com"],
        "rankings": "Inc 5000 Forbes Cloud 100 Deloitte Fast 500 Fortune 500",
        "language": "English"
    },
    
    # France
    "fr": {
        "name": "French Business Media",
        "domains": ["lesechos.fr", "bfmtv.com", "lexpansion.lexpress.fr", "maddyness.com", "frenchweb.fr"],
        "rankings": "FW500 Champions de la Croissance French Tech 120",
        "language": "French"
    },
    
    # Belgium
    "be": {
        "name": "Belgian Business Media",
        "domains": ["tijd.be", "lecho.be", "trends.be", "datanews.be"],
        "rankings": "Trends Gazellen Deloitte Fast 50 Belgium",
        "language": "Dutch/French"
    },
    
    # Spain
    "es": {
        "name": "Spanish Business Media",
        "domains": ["expansion.com", "cincodias.elpais.com", "eleconomista.es", "elpais.com/economia"],
        "rankings": "Actualidad Economica 500 Ranking Empresas",
        "language": "Spanish"
    },
    
    # Italy
    "it": {
        "name": "Italian Business Media",
        "domains": ["ilsole24ore.com", "corriere.it", "startupitalia.eu", "wired.it"],
        "rankings": "Il Sole 24 Ore Top 500 Italy",
        "language": "Italian"
    },
    
    # Sweden
    "se": {
        "name": "Swedish Business Media",
        "domains": ["di.se", "breakit.se", "svd.se", "nyteknik.se"],
        "rankings": "DI Gasell Sweden Fastest Growing",
        "language": "Swedish"
    },
    
    # Norway
    "no": {
        "name": "Norwegian Business Media",
        "domains": ["dn.no", "e24.no", "shifter.no"],
        "rankings": "Dagens Naeringsliv Gaselle",
        "language": "Norwegian"
    },
    
    # Denmark
    "dk": {
        "name": "Danish Business Media",
        "domains": ["borsen.dk", "finans.dk", "techsavvy.media"],
        "rankings": "Borsen Gazelle Denmark",
        "language": "Danish"
    },
    
    # Australia
    "au": {
        "name": "Australian Business Media",
        "domains": ["afr.com", "smartcompany.com.au", "businessnewsaustralia.com", "startupdaily.net"],
        "rankings": "AFR Fast 100 BRW Fast Starters Deloitte Fast 50 Australia",
        "language": "English"
    },
    
    # Canada
    "ca": {
        "name": "Canadian Business Media",
        "domains": ["bnn.ca", "theglobeandmail.com", "financialpost.com", "betakit.com"],
        "rankings": "Growth 500 Deloitte Fast 50 Canada",
        "language": "English"
    },
    
    # Singapore
    "sg": {
        "name": "Singapore Business Media",
        "domains": ["businesstimes.com.sg", "straitstimes.com", "techinasia.com"],
        "rankings": "Singapore Business Awards Fast Enterprise",
        "language": "English"
    },
    
    # India
    "in": {
        "name": "Indian Business Media",
        "domains": ["economictimes.indiatimes.com", "business-standard.com", "yourstory.com", "inc42.com"],
        "rankings": "ET 500 Fortune India 500",
        "language": "English"
    },
    
    # Default (Global English)
    "default": {
        "name": "Global Business Media",
        "domains": ["reuters.com", "bloomberg.com", "forbes.com", "techcrunch.com", "crunchbase.com"],
        "rankings": "Global 2000 Unicorn List Forbes Global",
        "language": "English"
    }
}

# Country name to code mapping
COUNTRY_CODE_MAP = {
    # Netherlands
    "netherlands": "nl", "nederland": "nl", "nl": "nl", "the netherlands": "nl", "holland": "nl",
    # Germany
    "germany": "de", "deutschland": "de", "de": "de", "duitsland": "de",
    # United Kingdom
    "united kingdom": "uk", "uk": "uk", "great britain": "uk", "england": "uk", "gb": "uk",
    # United States
    "united states": "us", "usa": "us", "us": "us", "america": "us", "united states of america": "us",
    # France
    "france": "fr", "fr": "fr", "frankrijk": "fr",
    # Belgium
    "belgium": "be", "belgie": "be", "belgië": "be", "be": "be", "belgique": "be",
    # Spain
    "spain": "es", "españa": "es", "es": "es", "spanje": "es",
    # Italy
    "italy": "it", "italia": "it", "it": "it", "italië": "it",
    # Sweden
    "sweden": "se", "sverige": "se", "se": "se", "zweden": "se",
    # Norway
    "norway": "no", "norge": "no", "no": "no", "noorwegen": "no",
    # Denmark
    "denmark": "dk", "danmark": "dk", "dk": "dk", "denemarken": "dk",
    # Australia
    "australia": "au", "au": "au",
    # Canada
    "canada": "ca", "ca": "ca",
    # Singapore
    "singapore": "sg", "sg": "sg",
    # India
    "india": "in", "in": "in",
    # Other common
    "austria": "at", "oostenrijk": "at", "at": "at",
    "switzerland": "ch", "zwitserland": "ch", "ch": "ch", "schweiz": "ch",
    "poland": "pl", "polen": "pl", "pl": "pl",
    "portugal": "pt", "pt": "pt",
    "ireland": "ie", "ierland": "ie", "ie": "ie",
    "finland": "fi", "fi": "fi",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SearchTopicResult:
    """Result from a single search topic."""
    topic: str
    success: bool
    data: str = ""
    results_count: int = 0
    error: str = ""


@dataclass
class ComprehensiveResearchResult:
    """Complete research result from all topics."""
    success: bool = False
    company_name: str = ""
    country: str = ""
    
    # Section results
    topics_completed: int = 0
    topics_failed: int = 0
    topic_results: Dict[str, SearchTopicResult] = field(default_factory=dict)
    
    # Combined markdown output
    markdown_output: str = ""
    
    # Metadata
    total_results: int = 0
    execution_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Exa Comprehensive Researcher
# =============================================================================

class ExaComprehensiveResearcher:
    """
    Comprehensive B2B research using Exa's Search, Answer, and Contents APIs.
    
    Uses 30 PARALLEL CALLS for STATE-OF-THE-ART coverage:
    
    COMPANY INFORMATION (4):
    1. company_identity - Name, founded, HQ, industry from LinkedIn/Crunchbase
    2. business_model - What they do, how they make money (website content)
    3. products_services - Detailed offerings, pricing
    4. financials_funding - Revenue, funding, investors
    
    PEOPLE (6):
    5. ceo_founder - CEO/Founder with LinkedIn
    6. c_suite - CFO, CTO, COO, CMO with LinkedIns
    7. senior_leadership - VPs, Directors
    8. board_advisors - Board members, investors
    9. leadership_changes - Recent hires, departures
    10. founder_story - Origin story, vision
    
    MARKET INTELLIGENCE (5):
    11. recent_news - Last 90 days
    12. partnerships_acquisitions - Deals, M&A
    13. hiring_signals - Job openings, growth
    14. technology_stack - CRM, cloud, tools
    15. competition - Competitors, positioning
    
    DEEP INSIGHTS (7):
    16. employee_reviews - Glassdoor, Indeed
    17. events_speaking - Conferences, webinars
    18. awards_recognition - Industry awards
    19. media_interviews - Podcasts, interviews
    20. customer_reviews - G2, Capterra
    21. challenges_priorities - Strategy, pain points
    22. certifications - ISO, SOC2, GDPR
    
    STRATEGIC INTELLIGENCE (6):
    23. key_customers - Named clients, case studies
    24. risk_signals - Lawsuits, controversies
    25. future_roadmap - Plans, expansion
    26. sustainability_esg - ESG, CSR
    27. patents_innovation - R&D, IP
    28. vendor_partners - Tech ecosystem
    
    LOCAL MARKET (2):
    29. local_media - Country-specific coverage
    30. local_rankings - Country-specific rankings
    """
    
    def __init__(self):
        """Initialize Exa client."""
        self._client = None
        self._initialized = False
        
        api_key = os.getenv("EXA_API_KEY")
        if api_key:
            try:
                from exa_py import Exa
                self._client = Exa(api_key=api_key)
                self._initialized = True
                logger.info("[EXA_COMPREHENSIVE] Service initialized")
            except ImportError:
                logger.warning("[EXA_COMPREHENSIVE] Exa SDK not available")
            except Exception as e:
                logger.warning(f"[EXA_COMPREHENSIVE] Failed to initialize: {e}")
        else:
            logger.info("[EXA_COMPREHENSIVE] No API key configured")
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._initialized and self._client is not None
    
    def _get_country_code(self, country: Optional[str]) -> str:
        """Get country code from country name."""
        if not country:
            return "default"
        return COUNTRY_CODE_MAP.get(country.lower().strip(), "default")
    
    def _get_local_sources(self, country: Optional[str]) -> Dict[str, Any]:
        """Get local business sources for a country."""
        code = self._get_country_code(country)
        return LOCAL_BUSINESS_SOURCES.get(code, LOCAL_BUSINESS_SOURCES["default"])
    
    def _get_90_days_ago(self) -> str:
        """Get ISO date string for 90 days ago."""
        return (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00.000Z")
    
    def _get_1_year_ago(self) -> str:
        """Get ISO date string for 1 year ago."""
        return (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00.000Z")
    
    async def _execute_search(
        self,
        topic: str,
        query: str,
        category: Optional[str] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        start_published_date: Optional[str] = None,
        num_results: int = 10,
        get_contents: bool = False,
        max_characters: int = 1500
    ) -> SearchTopicResult:
        """
        Execute a single search topic.
        
        Args:
            topic: Topic name for logging/tracking
            query: Search query
            category: Exa category filter (people, company, news, etc.)
            include_domains: Domains to include
            exclude_domains: Domains to exclude
            start_published_date: Only results after this date (ISO format)
            num_results: Number of results to return
            get_contents: Whether to fetch page contents
            max_characters: Max characters per result text
            
        Returns:
            SearchTopicResult with formatted data
        """
        if not self._client:
            return SearchTopicResult(
                topic=topic,
                success=False,
                error="Client not initialized"
            )
        
        try:
            loop = asyncio.get_event_loop()
            
            # Build search kwargs
            search_kwargs = {
                "query": query,
                "type": "auto",
                "num_results": num_results,
            }
            
            if category:
                search_kwargs["category"] = category
            
            if include_domains:
                search_kwargs["include_domains"] = include_domains
            
            if exclude_domains:
                search_kwargs["exclude_domains"] = exclude_domains
            
            if start_published_date:
                search_kwargs["start_published_date"] = start_published_date
            
            # Execute search
            if get_contents:
                search_kwargs["text"] = {"max_characters": max_characters}
                
                def do_search():
                    return self._client.search_and_contents(**search_kwargs)
            else:
                def do_search():
                    return self._client.search(**search_kwargs)
            
            response = await loop.run_in_executor(None, do_search)
            
            if not response.results:
                return SearchTopicResult(
                    topic=topic,
                    success=True,
                    data=f"No results found for: {query}",
                    results_count=0
                )
            
            # Format results as markdown
            lines = []
            lines.append(f"### {topic.replace('_', ' ').title()}\n")
            lines.append(f"*Query: {query}*\n")
            
            for i, result in enumerate(response.results, 1):
                url = getattr(result, 'url', '')
                title = getattr(result, 'title', 'Untitled')
                published = getattr(result, 'published_date', None) or getattr(result, 'publishedDate', '')
                text = getattr(result, 'text', '') if get_contents else ''
                
                lines.append(f"\n**{i}. [{title}]({url})**")
                if published:
                    lines.append(f"*Published: {published[:10] if len(published) > 10 else published}*")
                if text:
                    # Truncate text if too long
                    text_preview = text[:500] + "..." if len(text) > 500 else text
                    lines.append(f"\n{text_preview}")
            
            return SearchTopicResult(
                topic=topic,
                success=True,
                data="\n".join(lines),
                results_count=len(response.results)
            )
            
        except Exception as e:
            logger.error(f"[EXA_COMPREHENSIVE] {topic} search failed: {e}")
            return SearchTopicResult(
                topic=topic,
                success=False,
                error=str(e)
            )
    
    async def _execute_people_search(
        self,
        topic: str,
        query: str,
        num_results: int = 10
    ) -> SearchTopicResult:
        """
        Execute a people search (executives, leadership).
        
        Uses category="people" for Exa's 1B+ LinkedIn profile index.
        """
        return await self._execute_search(
            topic=topic,
            query=query,
            category="people",
            num_results=num_results,
            get_contents=False
        )
    
    async def _execute_news_search(
        self,
        topic: str,
        query: str,
        days_back: int = 90,
        num_results: int = 10
    ) -> SearchTopicResult:
        """
        Execute a news search with date filtering.
        """
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
        
        return await self._execute_search(
            topic=topic,
            query=query,
            category="news",
            start_published_date=start_date,
            num_results=num_results,
            get_contents=True,
            max_characters=1000
        )
    
    async def _execute_domain_search(
        self,
        topic: str,
        query: str,
        domains: List[str],
        num_results: int = 5,
        get_contents: bool = True
    ) -> SearchTopicResult:
        """
        Execute a domain-filtered search for quality sources.
        """
        return await self._execute_search(
            topic=topic,
            query=query,
            include_domains=domains,
            num_results=num_results,
            get_contents=get_contents,
            max_characters=2000
        )
    
    def _build_all_search_tasks(
        self,
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        linkedin_url: Optional[str],
        website_url: Optional[str]
    ) -> List[tuple]:
        """
        Build all 30 search tasks with their parameters.
        
        Returns list of (topic, coroutine) tuples.
        """
        tasks = []
        
        # Location context
        location_hint = ""
        if city and country:
            location_hint = f" {city} {country}"
        elif country:
            location_hint = f" {country}"
        
        # Get local sources
        local_sources = self._get_local_sources(country)
        
        # =========================================================================
        # SECTION 1: COMPANY INFORMATION (4 calls)
        # =========================================================================
        
        # 1. Company Identity
        tasks.append((
            "company_identity",
            self._execute_domain_search(
                topic="company_identity",
                query=f"{company_name} company founded headquarters industry employees",
                domains=["linkedin.com", "crunchbase.com", "wikipedia.org", "bloomberg.com"],
                num_results=5,
                get_contents=True
            )
        ))
        
        # 2. Business Model (website content)
        if website_url:
            tasks.append((
                "business_model",
                self._execute_domain_search(
                    topic="business_model",
                    query=f"{company_name} about services what we do business model",
                    domains=[website_url.replace("https://", "").replace("http://", "").split("/")[0]],
                    num_results=5,
                    get_contents=True
                )
            ))
        else:
            tasks.append((
                "business_model",
                self._execute_search(
                    topic="business_model",
                    query=f"{company_name} about us services business model what they do",
                    num_results=5,
                    get_contents=True
                )
            ))
        
        # 3. Products & Services
        tasks.append((
            "products_services",
            self._execute_search(
                topic="products_services",
                query=f"{company_name} products services solutions platform pricing",
                num_results=8,
                get_contents=True,
                max_characters=1500
            )
        ))
        
        # 4. Financials & Funding
        tasks.append((
            "financials_funding",
            self._execute_domain_search(
                topic="financials_funding",
                query=f"{company_name} funding revenue valuation series investment",
                domains=["crunchbase.com", "pitchbook.com", "techcrunch.com", "forbes.com", "dealroom.co"],
                num_results=5,
                get_contents=True
            )
        ))
        
        # =========================================================================
        # SECTION 2: PEOPLE & LEADERSHIP (6 calls)
        # =========================================================================
        
        # 5. CEO & Founder
        tasks.append((
            "ceo_founder",
            self._execute_people_search(
                topic="ceo_founder",
                query=f"CEO founder managing director at {company_name}{location_hint}",
                num_results=5
            )
        ))
        
        # 6. C-Suite
        tasks.append((
            "c_suite",
            self._execute_people_search(
                topic="c_suite",
                query=f"CFO CTO COO CMO CRO CHRO chief officer at {company_name}{location_hint}",
                num_results=10
            )
        ))
        
        # 7. Senior Leadership
        tasks.append((
            "senior_leadership",
            self._execute_people_search(
                topic="senior_leadership",
                query=f"VP Vice President Director Head of at {company_name}",
                num_results=10
            )
        ))
        
        # 8. Board & Advisors
        tasks.append((
            "board_advisors",
            self._execute_search(
                topic="board_advisors",
                query=f"{company_name} board of directors advisory investors shareholders",
                include_domains=["linkedin.com", "crunchbase.com", "pitchbook.com"],
                num_results=8,
                get_contents=True
            )
        ))
        
        # 9. Leadership Changes
        tasks.append((
            "leadership_changes",
            self._execute_news_search(
                topic="leadership_changes",
                query=f"{company_name} new CEO CFO CTO hired appointed joined leadership",
                days_back=365,
                num_results=5
            )
        ))
        
        # 10. Founder Story
        tasks.append((
            "founder_story",
            self._execute_search(
                topic="founder_story",
                query=f"{company_name} founder story origin how started why founded vision",
                num_results=5,
                get_contents=True
            )
        ))
        
        # =========================================================================
        # SECTION 3: MARKET INTELLIGENCE (5 calls)
        # =========================================================================
        
        # 11. Recent News
        tasks.append((
            "recent_news",
            self._execute_news_search(
                topic="recent_news",
                query=f"{company_name} news announcement launch",
                days_back=90,
                num_results=10
            )
        ))
        
        # 12. Partnerships & Acquisitions
        tasks.append((
            "partnerships_acquisitions",
            self._execute_search(
                topic="partnerships_acquisitions",
                query=f"{company_name} partnership acquisition merger deal alliance",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 13. Hiring Signals
        tasks.append((
            "hiring_signals",
            self._execute_search(
                topic="hiring_signals",
                query=f"{company_name} jobs careers hiring vacatures open positions we are hiring",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 14. Technology Stack
        tasks.append((
            "technology_stack",
            self._execute_domain_search(
                topic="technology_stack",
                query=f"{company_name} technology stack uses powered by",
                domains=["stackshare.io", "builtwith.com", "g2.com", "siftery.com"],
                num_results=5,
                get_contents=True
            )
        ))
        
        # 15. Competition
        tasks.append((
            "competition",
            self._execute_search(
                topic="competition",
                query=f"{company_name} competitors vs alternative comparison market share",
                num_results=10,
                get_contents=True
            )
        ))
        
        # =========================================================================
        # SECTION 4: DEEP INSIGHTS (7 calls)
        # =========================================================================
        
        # 16. Employee Reviews
        tasks.append((
            "employee_reviews",
            self._execute_domain_search(
                topic="employee_reviews",
                query=f"{company_name} reviews working culture",
                domains=["glassdoor.com", "indeed.com", "kununu.com", "comparably.com"],
                num_results=5,
                get_contents=True
            )
        ))
        
        # 17. Events & Speaking
        tasks.append((
            "events_speaking",
            self._execute_search(
                topic="events_speaking",
                query=f"{company_name} conference speaker event webinar summit presentation",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 18. Awards & Recognition
        tasks.append((
            "awards_recognition",
            self._execute_search(
                topic="awards_recognition",
                query=f"{company_name} award winner best ranking fastest growing recognition",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 19. Media & Interviews
        tasks.append((
            "media_interviews",
            self._execute_search(
                topic="media_interviews",
                query=f"{company_name} CEO founder interview podcast featured profile",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 20. Customer Reviews
        tasks.append((
            "customer_reviews",
            self._execute_domain_search(
                topic="customer_reviews",
                query=f"{company_name} reviews",
                domains=["g2.com", "capterra.com", "trustpilot.com", "softwareadvice.com", "getapp.com"],
                num_results=5,
                get_contents=True
            )
        ))
        
        # 21. Challenges & Priorities
        tasks.append((
            "challenges_priorities",
            self._execute_search(
                topic="challenges_priorities",
                query=f"{company_name} strategy priorities challenges transformation investing focus",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 22. Certifications
        tasks.append((
            "certifications",
            self._execute_search(
                topic="certifications",
                query=f"{company_name} ISO SOC2 GDPR certified compliance security certification",
                num_results=5,
                get_contents=True
            )
        ))
        
        # =========================================================================
        # SECTION 5: STRATEGIC INTELLIGENCE (6 calls)
        # =========================================================================
        
        # 23. Key Customers
        tasks.append((
            "key_customers",
            self._execute_search(
                topic="key_customers",
                query=f"{company_name} customers clients case study trusted by success story",
                num_results=10,
                get_contents=True
            )
        ))
        
        # 24. Risk Signals
        tasks.append((
            "risk_signals",
            self._execute_search(
                topic="risk_signals",
                query=f"{company_name} lawsuit layoffs controversy scandal problem issue",
                num_results=5,
                get_contents=True
            )
        ))
        
        # 25. Future Roadmap
        tasks.append((
            "future_roadmap",
            self._execute_search(
                topic="future_roadmap",
                query=f"{company_name} roadmap strategy 2025 plans expansion future vision",
                num_results=8,
                get_contents=True
            )
        ))
        
        # 26. Sustainability & ESG
        tasks.append((
            "sustainability_esg",
            self._execute_search(
                topic="sustainability_esg",
                query=f"{company_name} sustainability ESG carbon CSR duurzaamheid environmental",
                num_results=5,
                get_contents=True
            )
        ))
        
        # 27. Patents & Innovation
        tasks.append((
            "patents_innovation",
            self._execute_search(
                topic="patents_innovation",
                query=f"{company_name} patent innovation R&D research technology breakthrough",
                num_results=5,
                get_contents=True
            )
        ))
        
        # 28. Vendor Partners
        tasks.append((
            "vendor_partners",
            self._execute_search(
                topic="vendor_partners",
                query=f"{company_name} partner integration vendor ecosystem certified partner",
                num_results=8,
                get_contents=True
            )
        ))
        
        # =========================================================================
        # SECTION 6: LOCAL MARKET (2 calls - conditional)
        # =========================================================================
        
        # 29. Local Media
        if local_sources["domains"]:
            tasks.append((
                "local_media",
                self._execute_domain_search(
                    topic="local_media",
                    query=f"{company_name}",
                    domains=local_sources["domains"],
                    num_results=8,
                    get_contents=True
                )
            ))
        
        # 30. Local Rankings
        if local_sources["rankings"]:
            tasks.append((
                "local_rankings",
                self._execute_search(
                    topic="local_rankings",
                    query=f"{company_name} {local_sources['rankings']}",
                    num_results=5,
                    get_contents=True
                )
            ))
        
        return tasks
    
    async def research_company(
        self,
        company_name: str,
        country: Optional[str] = None,
        city: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None
    ) -> ComprehensiveResearchResult:
        """
        Execute comprehensive company research with 30 searches in rate-limited batches.
        
        Rate Limiting Strategy:
        - Exa has a 5 requests/second limit
        - We execute in batches of 4 with 250ms delay between batches
        - Total time: ~8 batches * 0.25s = ~2 seconds overhead
        - This ensures we stay well under the rate limit
        
        Args:
            company_name: Name of the company to research
            country: Country for local sources and context
            city: City for location context
            linkedin_url: Company LinkedIn URL
            website_url: Company website URL
            
        Returns:
            ComprehensiveResearchResult with all data
        """
        if not self.is_available:
            return ComprehensiveResearchResult(
                success=False,
                company_name=company_name,
                errors=["Service not available"]
            )
        
        start_time = datetime.now()
        
        logger.info(
            f"[EXA_COMPREHENSIVE] Starting research for {company_name} "
            f"(country={country}, city={city})"
        )
        
        # Build all search tasks
        task_definitions = self._build_all_search_tasks(
            company_name=company_name,
            country=country,
            city=city,
            linkedin_url=linkedin_url,
            website_url=website_url
        )
        
        logger.info(f"[EXA_COMPREHENSIVE] Executing {len(task_definitions)} searches in rate-limited batches")
        
        # Execute tasks in batches to respect Exa's 5 req/sec rate limit
        # Batch size of 4 with 250ms delay = safe margin under 5/sec
        BATCH_SIZE = 4
        BATCH_DELAY_SECONDS = 0.25
        
        results = []
        for batch_start in range(0, len(task_definitions), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(task_definitions))
            batch_tasks = task_definitions[batch_start:batch_end]
            
            # Execute this batch
            batch_coroutines = [task[1] for task in batch_tasks]
            batch_results = await asyncio.gather(*batch_coroutines, return_exceptions=True)
            results.extend(batch_results)
            
            # Log progress
            logger.info(f"[EXA_COMPREHENSIVE] Batch {batch_start//BATCH_SIZE + 1}/{(len(task_definitions) + BATCH_SIZE - 1)//BATCH_SIZE} complete ({batch_end}/{len(task_definitions)} topics)")
            
            # Delay before next batch (except for the last one)
            if batch_end < len(task_definitions):
                await asyncio.sleep(BATCH_DELAY_SECONDS)
        
        # Process results
        result = ComprehensiveResearchResult(
            company_name=company_name,
            country=country or ""
        )
        
        markdown_sections = []
        markdown_sections.append(f"# COMPREHENSIVE RESEARCH DATA FOR: {company_name}")
        markdown_sections.append(f"Research Date: {datetime.now().strftime('%d %B %Y')}")
        markdown_sections.append(f"Location: {city or 'Unknown'}, {country or 'Unknown'}")
        markdown_sections.append(f"Total Topics Searched: {len(task_definitions)}")
        markdown_sections.append("")
        
        # Section headers
        section_map = {
            "company_identity": "COMPANY INFORMATION",
            "ceo_founder": "PEOPLE & LEADERSHIP",
            "recent_news": "MARKET INTELLIGENCE",
            "employee_reviews": "DEEP INSIGHTS",
            "key_customers": "STRATEGIC INTELLIGENCE",
            "local_media": "LOCAL MARKET",
        }
        
        current_section = None
        
        for i, (topic_name, _) in enumerate(task_definitions):
            topic_result = results[i]
            
            # Check for section header
            if topic_name in section_map:
                current_section = section_map[topic_name]
                markdown_sections.append("")
                markdown_sections.append("=" * 60)
                markdown_sections.append(f"## {current_section}")
                markdown_sections.append("=" * 60)
                markdown_sections.append("")
            
            if isinstance(topic_result, Exception):
                logger.error(f"[EXA_COMPREHENSIVE] {topic_name} exception: {topic_result}")
                result.topic_results[topic_name] = SearchTopicResult(
                    topic=topic_name,
                    success=False,
                    error=str(topic_result)
                )
                result.topics_failed += 1
                result.errors.append(f"{topic_name}: {topic_result}")
                markdown_sections.append(f"\n### {topic_name.replace('_', ' ').title()}")
                markdown_sections.append(f"*Error: Search failed*\n")
            elif topic_result.success:
                result.topic_results[topic_name] = topic_result
                result.topics_completed += 1
                result.total_results += topic_result.results_count
                if topic_result.data:
                    markdown_sections.append(topic_result.data)
                    markdown_sections.append("")
            else:
                result.topic_results[topic_name] = topic_result
                result.topics_failed += 1
                if topic_result.error:
                    result.errors.append(f"{topic_name}: {topic_result.error}")
                markdown_sections.append(f"\n### {topic_name.replace('_', ' ').title()}")
                markdown_sections.append(f"*Error: {topic_result.error}*\n")
        
        # Add metadata section
        execution_time = (datetime.now() - start_time).total_seconds()
        result.execution_time_seconds = execution_time
        
        markdown_sections.append("")
        markdown_sections.append("---")
        markdown_sections.append("")
        markdown_sections.append("## RESEARCH METADATA")
        markdown_sections.append("")
        markdown_sections.append("| Metric | Value |")
        markdown_sections.append("|--------|-------|")
        markdown_sections.append(f"| Research Date | {datetime.now().strftime('%d %B %Y')} |")
        markdown_sections.append(f"| Company | {company_name} |")
        markdown_sections.append(f"| Location | {city or 'Unknown'}, {country or 'Unknown'} |")
        markdown_sections.append(f"| Total Topics | {len(task_definitions)} |")
        markdown_sections.append(f"| Successful | {result.topics_completed} |")
        markdown_sections.append(f"| Failed | {result.topics_failed} |")
        markdown_sections.append(f"| Total Results | {result.total_results} |")
        markdown_sections.append(f"| Execution Time | {execution_time:.1f}s |")
        
        if result.errors:
            markdown_sections.append(f"| Errors | {len(result.errors)} |")
        
        # Set success and combine output
        result.success = result.topics_completed > 0
        result.markdown_output = "\n".join(markdown_sections)
        
        logger.info(
            f"[EXA_COMPREHENSIVE] Research completed for {company_name}: "
            f"{result.topics_completed}/{len(task_definitions)} topics successful, "
            f"{result.total_results} total results, "
            f"{execution_time:.1f}s"
        )
        
        return result
    
    def format_for_claude(self, result: ComprehensiveResearchResult) -> str:
        """
        Format research result for Claude synthesis.
        
        Returns the markdown output which is already formatted.
        """
        return result.markdown_output


# =============================================================================
# Singleton Instance
# =============================================================================

_exa_comprehensive_researcher: Optional[ExaComprehensiveResearcher] = None


def get_exa_comprehensive_researcher() -> ExaComprehensiveResearcher:
    """Get or create the Exa Comprehensive Researcher singleton."""
    global _exa_comprehensive_researcher
    if _exa_comprehensive_researcher is None:
        _exa_comprehensive_researcher = ExaComprehensiveResearcher()
    return _exa_comprehensive_researcher


# =============================================================================
# Legacy aliases for backwards compatibility
# =============================================================================

# Keep old class name as alias
ExaResearchService = ExaComprehensiveResearcher


def get_exa_research_service() -> ExaComprehensiveResearcher:
    """Legacy alias for get_exa_comprehensive_researcher."""
    return get_exa_comprehensive_researcher()
