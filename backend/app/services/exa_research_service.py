"""
Exa Research Service - Comprehensive company research using Exa's Research API.

This service replaces the Gemini-first architecture with a single Exa Research API call
that returns structured JSON output for B2B sales intelligence.

Features:
- Async research with polling
- Structured JSON output schema
- Complete leadership, funding, and signals data
- Fallback to legacy Gemini-first flow
"""

import os
import asyncio
import logging
import httpx
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Output Schema for Company Research
# =============================================================================

COMPANY_RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {
            "type": "object",
            "properties": {
                "legal_name": {"type": "string"},
                "trading_name": {"type": "string"},
                "founded": {"type": "string"},
                "headquarters": {"type": "string"},
                "other_locations": {"type": "array", "items": {"type": "string"}},
                "industry": {"type": "string"},
                "sub_sector": {"type": "string"},
                "employee_range": {"type": "string"},
                "revenue_estimate": {"type": "string"},
                "description": {"type": "string"},
                "mission": {"type": "string"},
                "website": {"type": "string"},
                "linkedin_url": {"type": "string"}
            }
        },
        "leadership": {
            "type": "object",
            "properties": {
                "c_suite": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"},
                            "background": {"type": "string"},
                            "is_founder": {"type": "boolean"}
                        }
                    }
                },
                "senior_leadership": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"},
                            "department": {"type": "string"}
                        }
                    }
                },
                "board_of_directors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "affiliation": {"type": "string"}
                        }
                    }
                },
                "recent_changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "type": {"type": "string"},
                            "name": {"type": "string"},
                            "role": {"type": "string"}
                        }
                    }
                }
            }
        },
        "ownership_funding": {
            "type": "object",
            "properties": {
                "ownership_type": {"type": "string"},
                "parent_company": {"type": "string"},
                "major_shareholders": {"type": "array", "items": {"type": "string"}},
                "total_funding_raised": {"type": "string"},
                "funding_rounds": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "round_type": {"type": "string"},
                            "amount": {"type": "string"},
                            "lead_investor": {"type": "string"},
                            "other_investors": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "key_investors": {"type": "array", "items": {"type": "string"}},
                "acquisitions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "recent_news": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "headline": {"type": "string"},
                    "type": {"type": "string"},
                    "source_url": {"type": "string"}
                }
            }
        },
        "signals": {
            "type": "object",
            "properties": {
                "hiring_activity": {
                    "type": "object",
                    "properties": {
                        "job_openings_count": {"type": "string"},
                        "top_hiring_departments": {"type": "array", "items": {"type": "string"}},
                        "hiring_velocity": {"type": "string"}
                    }
                },
                "growth_signals": {"type": "array", "items": {"type": "string"}},
                "technology_stack": {
                    "type": "object",
                    "properties": {
                        "crm": {"type": "string"},
                        "cloud_provider": {"type": "string"},
                        "other_tools": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },
        "competitive_landscape": {
            "type": "object",
            "properties": {
                "main_competitors": {"type": "array", "items": {"type": "string"}},
                "market_position": {"type": "string"},
                "differentiators": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExecutiveInfo:
    """Executive/leadership information."""
    name: str
    title: str
    linkedin_url: str = ""
    background: str = ""
    is_founder: bool = False
    department: str = ""


@dataclass
class FundingRound:
    """Single funding round."""
    date: str
    round_type: str
    amount: str
    lead_investor: str = ""
    other_investors: List[str] = field(default_factory=list)


@dataclass
class NewsItem:
    """News/event item."""
    date: str
    headline: str
    news_type: str = ""
    source_url: str = ""


@dataclass
class CompanyResearchResult:
    """Complete company research result."""
    success: bool = False
    research_id: str = ""
    
    # Company basics
    company_name: str = ""
    legal_name: str = ""
    trading_name: str = ""
    founded: str = ""
    headquarters: str = ""
    other_locations: List[str] = field(default_factory=list)
    industry: str = ""
    sub_sector: str = ""
    employee_range: str = ""
    revenue_estimate: str = ""
    description: str = ""
    mission: str = ""
    website: str = ""
    linkedin_url: str = ""
    
    # Leadership
    c_suite: List[ExecutiveInfo] = field(default_factory=list)
    senior_leadership: List[ExecutiveInfo] = field(default_factory=list)
    board_of_directors: List[Dict[str, str]] = field(default_factory=list)
    leadership_changes: List[Dict[str, str]] = field(default_factory=list)
    
    # Ownership & Funding
    ownership_type: str = ""
    parent_company: str = ""
    major_shareholders: List[str] = field(default_factory=list)
    total_funding_raised: str = ""
    funding_rounds: List[FundingRound] = field(default_factory=list)
    key_investors: List[str] = field(default_factory=list)
    acquisitions: List[str] = field(default_factory=list)
    
    # News & Signals
    recent_news: List[NewsItem] = field(default_factory=list)
    job_openings_count: str = ""
    top_hiring_departments: List[str] = field(default_factory=list)
    hiring_velocity: str = ""
    growth_signals: List[str] = field(default_factory=list)
    
    # Technology
    crm: str = ""
    cloud_provider: str = ""
    other_tools: List[str] = field(default_factory=list)
    
    # Competitive
    main_competitors: List[str] = field(default_factory=list)
    market_position: str = ""
    differentiators: List[str] = field(default_factory=list)
    
    # Metadata
    cost_dollars: float = 0.0
    num_searches: int = 0
    num_pages: int = 0
    reasoning_tokens: int = 0
    errors: List[str] = field(default_factory=list)
    raw_output: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Exa Research Service
# =============================================================================

class ExaResearchService:
    """
    Service for comprehensive company research using Exa's Research API.
    
    Replaces Gemini-first architecture with structured JSON output.
    """
    
    BASE_URL = "https://api.exa.ai"
    
    def __init__(self):
        self._api_key = os.getenv("EXA_API_KEY")
        self._initialized = self._api_key is not None
        
        if self._initialized:
            logger.info("[EXA_RESEARCH] Service initialized")
        else:
            logger.warning("[EXA_RESEARCH] No API key found - service disabled")
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._initialized
    
    def _build_instructions(
        self,
        company_name: str,
        country: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None
    ) -> str:
        """Build research instructions for Exa."""
        location_context = f" ({country})" if country else ""
        linkedin_context = f"\nLinkedIn: {linkedin_url}" if linkedin_url else ""
        website_context = f"\nWebsite: {website_url}" if website_url else ""
        
        return f"""Research {company_name}{location_context} comprehensively for B2B sales intelligence.
{linkedin_context}{website_context}

1. COMPANY BASICS
   - Legal name and trading name (if different)
   - Founded date
   - Headquarters location
   - Other office locations
   - Industry and sub-sector
   - Employee count range
   - Estimated annual revenue (if available)
   - Company description and mission statement
   - Website URL
   - LinkedIn company URL

2. LEADERSHIP TEAM (CRITICAL - Include LinkedIn URLs)
   a) C-Suite Executives:
      - CEO/Managing Director with LinkedIn URL
      - CFO/Finance Director with LinkedIn URL
      - CTO/CIO with LinkedIn URL
      - COO with LinkedIn URL
      - CMO with LinkedIn URL
      - Other C-level executives
   b) Senior Leadership:
      - VPs and Directors with LinkedIn URLs
      - Department heads
   c) Board of Directors:
      - Board members with affiliations
      - Advisory board members if available
   d) Recent Leadership Changes (last 12 months):
      - New hires at executive level
      - Departures

3. OWNERSHIP & FUNDING
   a) Ownership Structure:
      - Private / Public / PE-backed / VC-backed / Family-owned
      - Parent company (if subsidiary)
      - Major shareholders
   b) Complete Funding History:
      - Total funding raised
      - Each funding round: date, type (Seed/Series A/B/C), amount, lead investor
      - Key investors with fund names
   c) Recent M&A Activity:
      - Acquisitions made
      - If they were acquired

4. RECENT NEWS & EVENTS (last 6 months)
   - Major announcements with dates and source URLs
   - Partnerships and collaborations
   - Product launches
   - Awards and recognition
   - Media coverage

5. BUSINESS SIGNALS
   a) Hiring Activity:
      - Current job openings count
      - Departments hiring most
      - Hiring velocity (growing/stable/shrinking)
   b) Growth Signals:
      - Expansion news
      - New market entry
      - New product lines
   c) Technology Stack (if discoverable):
      - CRM system
      - Cloud provider (AWS/Azure/GCP)
      - Key technology vendors

6. COMPETITIVE LANDSCAPE
   - Main competitors
   - Market positioning (leader/challenger/niche)
   - Key differentiators
"""
    
    async def start_research(
        self,
        company_name: str,
        country: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None,
        model: str = "exa-research"
    ) -> Dict[str, Any]:
        """
        Start an async research task.
        
        Args:
            company_name: Company to research
            country: Country for regional context
            linkedin_url: Company LinkedIn URL
            website_url: Company website URL
            model: exa-research (faster) or exa-research-pro (more thorough)
            
        Returns:
            Dict with research_id for polling
        """
        if not self.is_available:
            return {"success": False, "error": "Service not available"}
        
        instructions = self._build_instructions(
            company_name, country, linkedin_url, website_url
        )
        
        payload = {
            "model": model,
            "instructions": instructions,
            "outputSchema": COMPANY_RESEARCH_SCHEMA
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/research/v1",
                    headers={
                        "x-api-key": self._api_key,
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                research_id = data.get("researchId")
                status = data.get("status")
                
                logger.info(
                    f"[EXA_RESEARCH] Started research for {company_name}: "
                    f"id={research_id}, status={status}"
                )
                
                return {
                    "success": True,
                    "research_id": research_id,
                    "status": status,
                    "company_name": company_name
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[EXA_RESEARCH] HTTP error starting research: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"[EXA_RESEARCH] Error starting research: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_research_status(self, research_id: str) -> Dict[str, Any]:
        """
        Get the status of a research task.
        
        Returns:
            Dict with status (pending/running/completed/failed) and output if complete
        """
        if not self.is_available:
            return {"success": False, "error": "Service not available"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/research/v1/{research_id}",
                    headers={"x-api-key": self._api_key}
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"[EXA_RESEARCH] Error getting status: {e}")
            return {"success": False, "error": str(e), "status": "error"}
    
    async def poll_until_complete(
        self,
        research_id: str,
        max_wait_seconds: int = 180,
        poll_interval: float = 5.0
    ) -> Dict[str, Any]:
        """
        Poll research status until complete or timeout.
        
        Args:
            research_id: Research task ID
            max_wait_seconds: Maximum time to wait
            poll_interval: Seconds between polls
            
        Returns:
            Complete research result or error
        """
        start_time = datetime.now()
        
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                logger.warning(f"[EXA_RESEARCH] Timeout after {elapsed:.1f}s")
                return {
                    "success": False,
                    "error": f"Timeout after {max_wait_seconds}s",
                    "status": "timeout"
                }
            
            result = await self.get_research_status(research_id)
            status = result.get("status")
            
            if status == "completed":
                logger.info(f"[EXA_RESEARCH] Research completed in {elapsed:.1f}s")
                return result
            
            if status == "failed":
                error = result.get("error", "Unknown error")
                logger.error(f"[EXA_RESEARCH] Research failed: {error}")
                return result
            
            if status == "canceled":
                logger.warning("[EXA_RESEARCH] Research was canceled")
                return result
            
            # Still running - wait and poll again
            logger.debug(f"[EXA_RESEARCH] Status: {status}, elapsed: {elapsed:.1f}s")
            await asyncio.sleep(poll_interval)
    
    def parse_result(self, raw_result: Dict[str, Any]) -> CompanyResearchResult:
        """
        Parse raw Exa Research API result into structured dataclass.
        
        Args:
            raw_result: Raw API response
            
        Returns:
            CompanyResearchResult with all fields populated
        """
        result = CompanyResearchResult()
        result.research_id = raw_result.get("researchId", "")
        result.raw_output = raw_result
        
        # Check for completion
        if raw_result.get("status") != "completed":
            result.success = False
            result.errors.append(raw_result.get("error", "Research not completed"))
            return result
        
        # Get output
        output = raw_result.get("output", {})
        parsed = output.get("parsed", {})
        
        if not parsed:
            # Try to parse from content string
            content = output.get("content", "")
            if content:
                try:
                    import json
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    result.errors.append("Could not parse output JSON")
                    return result
        
        result.success = True
        
        # Cost info
        cost_info = raw_result.get("costDollars", {})
        result.cost_dollars = cost_info.get("total", 0)
        result.num_searches = cost_info.get("numSearches", 0)
        result.num_pages = cost_info.get("numPages", 0)
        result.reasoning_tokens = cost_info.get("reasoningTokens", 0)
        
        # Company basics
        company = parsed.get("company", {})
        result.legal_name = company.get("legal_name", "")
        result.trading_name = company.get("trading_name", "")
        result.company_name = result.trading_name or result.legal_name
        result.founded = company.get("founded", "")
        result.headquarters = company.get("headquarters", "")
        result.other_locations = company.get("other_locations", [])
        result.industry = company.get("industry", "")
        result.sub_sector = company.get("sub_sector", "")
        result.employee_range = company.get("employee_range", "")
        result.revenue_estimate = company.get("revenue_estimate", "")
        result.description = company.get("description", "")
        result.mission = company.get("mission", "")
        result.website = company.get("website", "")
        result.linkedin_url = company.get("linkedin_url", "")
        
        # Leadership
        leadership = parsed.get("leadership", {})
        
        for exec_data in leadership.get("c_suite", []):
            result.c_suite.append(ExecutiveInfo(
                name=exec_data.get("name", ""),
                title=exec_data.get("title", ""),
                linkedin_url=exec_data.get("linkedin_url", ""),
                background=exec_data.get("background", ""),
                is_founder=exec_data.get("is_founder", False)
            ))
        
        for exec_data in leadership.get("senior_leadership", []):
            result.senior_leadership.append(ExecutiveInfo(
                name=exec_data.get("name", ""),
                title=exec_data.get("title", ""),
                linkedin_url=exec_data.get("linkedin_url", ""),
                department=exec_data.get("department", "")
            ))
        
        result.board_of_directors = leadership.get("board_of_directors", [])
        result.leadership_changes = leadership.get("recent_changes", [])
        
        # Ownership & Funding
        funding = parsed.get("ownership_funding", {})
        result.ownership_type = funding.get("ownership_type", "")
        result.parent_company = funding.get("parent_company", "")
        result.major_shareholders = funding.get("major_shareholders", [])
        result.total_funding_raised = funding.get("total_funding_raised", "")
        result.key_investors = funding.get("key_investors", [])
        result.acquisitions = funding.get("acquisitions", [])
        
        for round_data in funding.get("funding_rounds", []):
            result.funding_rounds.append(FundingRound(
                date=round_data.get("date", ""),
                round_type=round_data.get("round_type", ""),
                amount=round_data.get("amount", ""),
                lead_investor=round_data.get("lead_investor", ""),
                other_investors=round_data.get("other_investors", [])
            ))
        
        # News
        for news_data in parsed.get("recent_news", []):
            result.recent_news.append(NewsItem(
                date=news_data.get("date", ""),
                headline=news_data.get("headline", ""),
                news_type=news_data.get("type", ""),
                source_url=news_data.get("source_url", "")
            ))
        
        # Signals
        signals = parsed.get("signals", {})
        hiring = signals.get("hiring_activity", {})
        result.job_openings_count = hiring.get("job_openings_count", "")
        result.top_hiring_departments = hiring.get("top_hiring_departments", [])
        result.hiring_velocity = hiring.get("hiring_velocity", "")
        result.growth_signals = signals.get("growth_signals", [])
        
        tech = signals.get("technology_stack", {})
        result.crm = tech.get("crm", "")
        result.cloud_provider = tech.get("cloud_provider", "")
        result.other_tools = tech.get("other_tools", [])
        
        # Competitive
        competitive = parsed.get("competitive_landscape", {})
        result.main_competitors = competitive.get("main_competitors", [])
        result.market_position = competitive.get("market_position", "")
        result.differentiators = competitive.get("differentiators", [])
        
        return result
    
    async def research_company(
        self,
        company_name: str,
        country: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None,
        model: str = "exa-research",
        max_wait_seconds: int = 180
    ) -> CompanyResearchResult:
        """
        Complete company research workflow: start, poll, parse.
        
        This is the main entry point for company research.
        
        Args:
            company_name: Company to research
            country: Country for regional context
            linkedin_url: Company LinkedIn URL
            website_url: Company website URL
            model: exa-research or exa-research-pro
            max_wait_seconds: Maximum time to wait for completion
            
        Returns:
            CompanyResearchResult with all data
        """
        logger.info(f"[EXA_RESEARCH] Starting research for {company_name}")
        
        # Start research
        start_result = await self.start_research(
            company_name, country, linkedin_url, website_url, model
        )
        
        if not start_result.get("success"):
            result = CompanyResearchResult()
            result.errors.append(start_result.get("error", "Failed to start research"))
            return result
        
        research_id = start_result["research_id"]
        
        # Poll until complete
        raw_result = await self.poll_until_complete(
            research_id, max_wait_seconds
        )
        
        # Parse result
        return self.parse_result(raw_result)
    
    def format_for_claude(self, result: CompanyResearchResult) -> str:
        """
        Format research result as markdown for Claude synthesis.
        
        Args:
            result: Parsed research result
            
        Returns:
            Markdown formatted string
        """
        sections = []
        
        # Company info
        sections.append("## COMPANY INFORMATION (from Exa Research)")
        sections.append("")
        sections.append(f"**Company**: {result.company_name or result.legal_name}")
        if result.trading_name and result.trading_name != result.legal_name:
            sections.append(f"**Trading As**: {result.trading_name}")
        sections.append(f"**Industry**: {result.industry} - {result.sub_sector}")
        sections.append(f"**Founded**: {result.founded}")
        sections.append(f"**Headquarters**: {result.headquarters}")
        if result.other_locations:
            sections.append(f"**Other Locations**: {', '.join(result.other_locations)}")
        sections.append(f"**Employees**: {result.employee_range}")
        if result.revenue_estimate:
            sections.append(f"**Revenue Estimate**: {result.revenue_estimate}")
        sections.append(f"**Website**: {result.website}")
        sections.append(f"**LinkedIn**: {result.linkedin_url}")
        sections.append("")
        sections.append(f"**Description**: {result.description}")
        if result.mission:
            sections.append(f"**Mission**: {result.mission}")
        sections.append("")
        
        # Leadership
        sections.append("## LEADERSHIP TEAM")
        sections.append("")
        
        if result.c_suite:
            sections.append("### C-Suite Executives")
            sections.append("| Name | Title | LinkedIn | Founder? |")
            sections.append("|------|-------|----------|----------|")
            for exec in result.c_suite:
                founder = "Yes" if exec.is_founder else ""
                sections.append(f"| {exec.name} | {exec.title} | {exec.linkedin_url} | {founder} |")
            sections.append("")
        
        if result.senior_leadership:
            sections.append("### Senior Leadership")
            sections.append("| Name | Title | Department | LinkedIn |")
            sections.append("|------|-------|------------|----------|")
            for exec in result.senior_leadership:
                sections.append(f"| {exec.name} | {exec.title} | {exec.department} | {exec.linkedin_url} |")
            sections.append("")
        
        if result.board_of_directors:
            sections.append("### Board of Directors")
            sections.append("| Name | Role | Affiliation |")
            sections.append("|------|------|-------------|")
            for member in result.board_of_directors:
                sections.append(f"| {member.get('name', '')} | {member.get('role', '')} | {member.get('affiliation', '')} |")
            sections.append("")
        
        if result.leadership_changes:
            sections.append("### Recent Leadership Changes")
            for change in result.leadership_changes:
                sections.append(f"- {change.get('date', '')}: {change.get('type', '')} - {change.get('name', '')} ({change.get('role', '')})")
            sections.append("")
        
        # Funding
        sections.append("## OWNERSHIP & FUNDING")
        sections.append("")
        sections.append(f"**Ownership Type**: {result.ownership_type}")
        if result.parent_company:
            sections.append(f"**Parent Company**: {result.parent_company}")
        if result.major_shareholders:
            sections.append(f"**Major Shareholders**: {', '.join(result.major_shareholders)}")
        sections.append(f"**Total Funding Raised**: {result.total_funding_raised}")
        
        if result.funding_rounds:
            sections.append("")
            sections.append("### Funding Rounds")
            sections.append("| Date | Round | Amount | Lead Investor |")
            sections.append("|------|-------|--------|---------------|")
            for round in result.funding_rounds:
                sections.append(f"| {round.date} | {round.round_type} | {round.amount} | {round.lead_investor} |")
        
        if result.key_investors:
            sections.append("")
            sections.append(f"**Key Investors**: {', '.join(result.key_investors)}")
        
        if result.acquisitions:
            sections.append("")
            sections.append(f"**Acquisitions**: {', '.join(result.acquisitions)}")
        sections.append("")
        
        # News
        if result.recent_news:
            sections.append("## RECENT NEWS & EVENTS")
            sections.append("")
            sections.append("| Date | Headline | Type | Source |")
            sections.append("|------|----------|------|--------|")
            for news in result.recent_news:
                sections.append(f"| {news.date} | {news.headline} | {news.news_type} | {news.source_url} |")
            sections.append("")
        
        # Signals
        sections.append("## BUSINESS SIGNALS")
        sections.append("")
        sections.append("### Hiring Activity")
        sections.append(f"- **Job Openings**: {result.job_openings_count}")
        sections.append(f"- **Hiring Velocity**: {result.hiring_velocity}")
        if result.top_hiring_departments:
            sections.append(f"- **Top Hiring Departments**: {', '.join(result.top_hiring_departments)}")
        
        if result.growth_signals:
            sections.append("")
            sections.append("### Growth Signals")
            for signal in result.growth_signals:
                sections.append(f"- {signal}")
        
        sections.append("")
        sections.append("### Technology Stack")
        if result.crm:
            sections.append(f"- **CRM**: {result.crm}")
        if result.cloud_provider:
            sections.append(f"- **Cloud Provider**: {result.cloud_provider}")
        if result.other_tools:
            sections.append(f"- **Other Tools**: {', '.join(result.other_tools)}")
        sections.append("")
        
        # Competitive
        sections.append("## COMPETITIVE LANDSCAPE")
        sections.append("")
        sections.append(f"**Market Position**: {result.market_position}")
        if result.main_competitors:
            sections.append(f"**Main Competitors**: {', '.join(result.main_competitors)}")
        if result.differentiators:
            sections.append("")
            sections.append("**Key Differentiators**:")
            for diff in result.differentiators:
                sections.append(f"- {diff}")
        sections.append("")
        
        # Metadata
        sections.append("---")
        sections.append(f"*Research cost: ${result.cost_dollars:.4f} | Searches: {result.num_searches} | Pages: {result.num_pages}*")
        
        return "\n".join(sections)


# =============================================================================
# Module-level instance
# =============================================================================

_exa_research_service: Optional[ExaResearchService] = None


def get_exa_research_service() -> ExaResearchService:
    """Get or create the Exa Research Service instance."""
    global _exa_research_service
    if _exa_research_service is None:
        _exa_research_service = ExaResearchService()
    return _exa_research_service
