"""
Research orchestrator - coordinates multiple research sources.

Enhanced with full context awareness:
- Sales profile context (who is selling)
- Company profile context (what are we selling)
- Knowledge Base integration (case studies, product info)
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from supabase import Client
from .claude_researcher import ClaudeResearcher
from .gemini_researcher import GeminiResearcher
from .kvk_api import KVKApi
from .website_scraper import get_website_scraper
from app.database import get_supabase_service
from app.i18n.utils import get_language_instruction
from app.i18n.config import DEFAULT_LANGUAGE
from app.utils.timeout import with_timeout, AITimeoutError

logger = logging.getLogger(__name__)

# Timeout settings for research operations (in seconds)
RESEARCH_TASK_TIMEOUT = 60  # Individual AI task timeout
RESEARCH_TOTAL_TIMEOUT = 180  # Total research timeout (3 minutes)


class ResearchOrchestrator:
    """Orchestrate research from multiple sources with full context."""
    
    def __init__(self):
        """Initialize all research services."""
        self.claude = ClaudeResearcher()
        self.gemini = GeminiResearcher()
        self.kvk = KVKApi()
        self.website_scraper = get_website_scraper()
        
        # Initialize Supabase using centralized module
        self.supabase: Client = get_supabase_service()
    
    async def research_company(
        self,
        company_name: str,
        country: Optional[str] = None,
        city: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website_url: Optional[str] = None,
        organization_id: Optional[str] = None,  # NEW: For context
        user_id: Optional[str] = None,  # NEW: For sales profile
        language: str = DEFAULT_LANGUAGE  # i18n: output language
    ) -> Dict[str, Any]:
        """
        Research company using multiple sources in parallel.
        
        Enhanced with full context awareness:
        - Sales profile (who is selling, their strengths)
        - Company profile (what we sell, value propositions)
        - Knowledge Base (case studies, product info)
        
        Args:
            company_name: Name of the company
            country: Optional country
            city: Optional city
            linkedin_url: Optional LinkedIn URL
            website_url: Optional website URL for direct scraping
            organization_id: Organization ID for context retrieval
            user_id: User ID for sales profile context
            language: Output language code (default: nl)
            
        Returns:
            Dictionary with combined research data
        """
        # Get seller context for personalized research
        seller_context = await self._get_seller_context(organization_id, user_id)
        
        # Determine which sources to use
        tasks = []
        source_names = []
        
        # Always use Claude and Gemini - now with seller context and language!
        tasks.append(self.claude.search_company(
            company_name, country, city, linkedin_url,
            seller_context=seller_context,
            language=language
        ))
        source_names.append("claude")
        
        tasks.append(self.gemini.search_company(
            company_name, country, city, linkedin_url,
            seller_context=seller_context,
            language=language
        ))
        source_names.append("gemini")
        
        # Use KVK only for Dutch companies
        if self.kvk.is_dutch_company(country):
            tasks.append(self.kvk.search_company(company_name, city))
            source_names.append("kvk")
        
        # NEW: Use website scraper if URL provided
        if website_url:
            tasks.append(self.website_scraper.scrape_website(website_url))
            source_names.append("website")
        
        # Execute all searches in parallel with timeout
        try:
            results = await with_timeout(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout_seconds=RESEARCH_TOTAL_TIMEOUT,
                operation_name="Research parallel tasks"
            )
        except AITimeoutError:
            logger.error(f"Research timed out after {RESEARCH_TOTAL_TIMEOUT}s for {company_name}")
            # Return partial results with timeout errors
            results = [asyncio.TimeoutError("Research timed out")] * len(tasks)
        
        # Combine results
        combined_data = {
            "sources": {},
            "success_count": 0,
            "total_sources": len(tasks)
        }
        
        for source_name, result in zip(source_names, results):
            if isinstance(result, Exception):
                combined_data["sources"][source_name] = {
                    "success": False,
                    "error": str(result)
                }
            else:
                combined_data["sources"][source_name] = result
                if result.get("success"):
                    combined_data["success_count"] += 1
        
        # Get relevant KB chunks for case studies
        kb_chunks = []
        if organization_id:
            kb_chunks = await self._get_relevant_kb_chunks(
                company_name, organization_id, seller_context
            )
            if kb_chunks:
                combined_data["sources"]["knowledge_base"] = {
                    "success": True,
                    "data": kb_chunks
                }
                combined_data["success_count"] += 1
        
        # Generate unified brief with full context
        combined_data["brief"] = await self._generate_unified_brief(
            combined_data["sources"],
            company_name,
            country,
            city,
            seller_context=seller_context,
            kb_chunks=kb_chunks,
            language=language
        )
        
        return combined_data
    
    async def _get_seller_context(
        self,
        organization_id: Optional[str],
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Get seller context: who is selling, what are they selling.
        
        This context makes research prompts highly personalized.
        Extracts and flattens fields from company_profile and sales_profile.
        """
        context = {
            "has_context": False,
            "company_name": None,
            "industry": None,
            "products_services": [],
            "value_propositions": [],
            "target_market": "B2B",
            "target_industries": [],
            "differentiators": [],
            "sales_person": None,
            "sales_strengths": [],
            "company_narrative": None,
            "sales_narrative": None
        }
        
        if not organization_id:
            return context
        
        try:
            # Get company profile
            company_response = self.supabase.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .limit(1)\
                .execute()
            
            if company_response.data:
                company = company_response.data[0]
                context["has_context"] = True
                context["company_name"] = company.get("company_name")
                context["industry"] = company.get("industry")
                
                # Products: extract names from products array
                products = company.get("products", []) or []
                context["products_services"] = [
                    p.get("name") for p in products 
                    if isinstance(p, dict) and p.get("name")
                ]
                
                # Value propositions from core_value_props
                context["value_propositions"] = company.get("core_value_props", []) or []
                
                # Differentiators (this field exists directly)
                context["differentiators"] = company.get("differentiators", []) or []
                
                # Target industries from Ideal Customer Profile
                icp = company.get("ideal_customer_profile", {}) or {}
                context["target_industries"] = icp.get("industries", []) or []
                
                context["company_narrative"] = company.get("company_narrative")
                
                logger.info(f"Seller context from company_profile: {context['company_name']}, products={len(context['products_services'])}")
            
            # Get sales profile
            if user_id:
                sales_response = self.supabase.table("sales_profiles")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .limit(1)\
                    .execute()
                
                if sales_response.data:
                    sales = sales_response.data[0]
                    context["sales_person"] = sales.get("full_name")
                    context["sales_strengths"] = sales.get("strengths", []) or []
                    context["sales_narrative"] = sales.get("sales_narrative")
                    
                    # Fallback: extract company name from role if not set
                    if not context.get("company_name"):
                        role = sales.get("role", "") or ""
                        if " at " in role:
                            context["company_name"] = role.split(" at ")[-1].strip()
                            context["has_context"] = True
                            logger.info(f"Extracted company from sales_profile role: {context['company_name']}")
                    
                    # Fallback: target industries from sales profile
                    if not context.get("target_industries"):
                        context["target_industries"] = sales.get("target_industries", []) or []
            
            logger.info(f"Loaded seller context: {context['company_name']}, has_context={context['has_context']}")
            
        except Exception as e:
            logger.warning(f"Could not load seller context: {e}")
        
        return context
    
    async def _get_relevant_kb_chunks(
        self,
        prospect_company: str,
        organization_id: str,
        seller_context: Dict[str, Any],
        max_chunks: int = 3
    ) -> List[Dict[str, str]]:
        """
        Get relevant KB chunks (case studies, product info) for the prospect.
        """
        try:
            from app.services.embeddings import EmbeddingsService
            from app.services.vector_store import VectorStore
            
            embeddings = EmbeddingsService()
            vector_store = VectorStore()
            
            # Build query based on prospect and what we sell
            products = ", ".join(seller_context.get("products_services", [])[:3])
            query = f"{prospect_company} case study success {products}"
            
            query_embedding = await embeddings.embed_text(query)
            
            matches = vector_store.query_vectors(
                query_vector=query_embedding,
                filter={"organization_id": organization_id},
                top_k=max_chunks,
                include_metadata=True
            )
            
            chunks = []
            for match in matches:
                if match.score > 0.5:  # Only include relevant chunks
                    chunks.append({
                        "text": match.metadata.get("text", "")[:500],
                        "source": match.metadata.get("filename", "Document"),
                        "score": match.score
                    })
            
            logger.info(f"Found {len(chunks)} relevant KB chunks for {prospect_company}")
            return chunks
            
        except Exception as e:
            logger.warning(f"Error getting KB chunks: {e}")
            return []
    
    async def _generate_unified_brief(
        self,
        sources: Dict[str, Any],
        company_name: str,
        country: Optional[str],
        city: Optional[str],
        seller_context: Optional[Dict[str, Any]] = None,
        kb_chunks: Optional[List[Dict[str, str]]] = None,
        language: str = DEFAULT_LANGUAGE
    ) -> str:
        """
        Generate unified research brief from all sources.
        
        Enhanced with seller context for personalized talking points.
        """
        lang_instruction = get_language_instruction(language)
        # Collect successful source data
        source_data = []
        
        if sources.get("claude", {}).get("success"):
            source_data.append(f"## Claude Research:\n{sources['claude']['data']}")
        
        if sources.get("gemini", {}).get("success"):
            source_data.append(f"## Gemini Research:\n{sources['gemini']['data']}")
        
        if sources.get("kvk", {}).get("success"):
            kvk_data = sources['kvk']['data']
            kvk_text = f"""## KVK Official Data:
- KVK Number: {kvk_data.get('kvk_number')}
- Legal Form: {kvk_data.get('legal_form')}
- Trade Name: {kvk_data.get('trade_name')}
- Address: {kvk_data.get('address', {}).get('street')} {kvk_data.get('address', {}).get('house_number')}, {kvk_data.get('address', {}).get('postal_code')} {kvk_data.get('address', {}).get('city')}
- Established: {kvk_data.get('establishment_date')}
- Employees: {kvk_data.get('employees')}
- Website: {kvk_data.get('website')}
"""
            source_data.append(kvk_text)
        
        # Add website scraper data
        if sources.get("website", {}).get("success"):
            website_data = sources['website']
            website_text = f"""## Company Website Content:
**URL**: {website_data.get('url')}
**Pages Scraped**: {website_data.get('pages_scraped', 0)}

{website_data.get('summary', 'No summary available')}
"""
            source_data.append(website_text)
        
        if not source_data:
            return "# Research Failed\n\nNo data found from sources."
        
        # Build seller context section for the prompt
        seller_section = ""
        if seller_context and seller_context.get("has_context"):
            products = ", ".join(seller_context.get("products_services", [])[:5]) or "Not specified"
            values = ", ".join(seller_context.get("value_propositions", [])[:3]) or "Not specified"
            diffs = ", ".join(seller_context.get("differentiators", [])[:3]) or "Not specified"
            
            seller_section = f"""
## CONTEXT: WHAT YOU SELL
**Your company**: {seller_context.get('company_name', 'Unknown')}
**Products/Services**: {products}
**Value Propositions**: {values}
**Differentiators**: {diffs}
**Target Market**: {seller_context.get('target_market', 'Not specified')}
"""
        
        # Build KB context section
        kb_section = ""
        if kb_chunks:
            kb_texts = "\n".join([
                f"- **{chunk['source']}**: {chunk['text'][:200]}..."
                for chunk in kb_chunks
            ])
            kb_section = f"""
## RELEVANT CASE STUDIES/DOCUMENTS FROM YOUR KNOWLEDGE BASE:
{kb_texts}
"""
        
        # Build KB references section for the prompt
        kb_references = ""
        if kb_chunks:
            kb_references = chr(10).join([f"| {chunk['source']} | [Relevance] |" for chunk in kb_chunks])
        else:
            kb_references = "| — | — |"
        
        # Pre-calculate source status for the Research Confidence table
        claude_status = "✅" if sources.get("claude", {}).get("success") else "❌"
        gemini_status = "✅" if sources.get("gemini", {}).get("success") else "❌"
        kvk_status = "✅" if sources.get("kvk", {}).get("success") else ("N/A" if "kvk" not in sources else "❌")
        website_status = "✅" if sources.get("website", {}).get("success") else ("N/A" if "website" not in sources else "❌")
        kb_status = f"✅ {len(kb_chunks)} matches" if kb_chunks else "❌ No matches"
        
        # Use Claude to merge the data - with seller context and language instruction
        merge_prompt = f"""You are a senior sales intelligence analyst preparing a strategic prospect brief.

Write in clear, sharp and commercially relevant language.

Your tone should reflect strategic insight, market awareness and sales acumen.

Every insight must be grounded in the provided source data, never invented.

Your goal:
Give the sales professional a full understanding of the prospect's world and the commercial fit in **5 minutes of reading**.
Provide intelligence, not data dumps.

{seller_section}
{kb_section}

I have collected information about {company_name} from multiple sources:

{chr(10).join(source_data)}

---

Generate a research brief with EXACTLY this structure:

# Research Brief: {company_name}
{f"📍 {city}, {country}" if city and country else ""}

---

## 📋 In One Sentence

A precise sentence explaining:
- who this company is
- what makes them commercially relevant
- why this might be the right time to engage

Focus on relevance and opportunity, not generic descriptions.

---

## 📊 At a Glance

| Aspect | Assessment |
|--------|------------|
| **Opportunity Fit** | 🟢 High / 🟡 Medium / 🔴 Low — [based on the seller's offerings] |
| **Timing** | 🟢 NOW / 🟡 Nurture / 🔴 No Focus — [based on evidence] |
| **Company Stage** | Startup / Scale-up / SMB / Enterprise |
| **Industry Match** | 🟢 Core / 🟡 Adjacent / 🔴 Outside Target |
| **Primary Risk** | [The main commercial or structural obstacle] |

This gives the rep a one-screen strategic snapshot.

---

## 🏢 Company Profile

| Element | Details |
|---------|---------|
| **Industry** | [Sector + sub-sector] |
| **Size** | [Employees, revenue if verified] |
| **Headquarters** | [Location] |
| **Founded** | [Year] |
| **Website** | [URL] |
| **Company ID** | [Chamber of Commerce / registration number if available] |

**What This Means Commercially**
One concise sentence linking their profile to the seller's potential relevance.

---

## 💼 Business Model

### What They Do
A tight 2–3 sentence explanation.

### Revenue Model

| Stream | Description |
|--------|-------------|
| [Stream 1] | [How it works] |
| [Stream 2] | [How it works] |

### Customers & Segments
- **Market Type**: [B2B / B2C / Mixed]
- **Customer Types**: [Enterprise / SMB / Consumer]
- **Industries Served**: [Key verticals]

### Their Value Proposition
- [What they promise]
- [How they differentiate]

**Commercial Insight**
What their model suggests about priorities, constraints or buying behaviour.

---

## 📰 Recent Developments (Last 90 Days)

### News & Signals

| Date | Development | Type |
|------|-------------|------|
| [Date] | [Update] | 📈 Growth / 💰 Funding / 👥 Leadership / 🚀 Product / 🤝 Partnership |
| ... | ... | ... |

### What These Signals Suggest
Interpret clearly:
- What are they prioritising?
- What pressure are they under?
- Where might they invest next?
- What might be changing internally?

Make this **evidence-led**, not speculative.

---

## 👥 Key People

### Leadership Team

| Name | Role | Background | LinkedIn |
|------|------|------------|----------|
| [Name] | [Title] | [Relevant highlights] | [URL] |

### Likely Decision Structure
Based on company size, industry and signals:
- **Decision Style**: [Top-down / Consensus / Committee / Pragmatic]
- **Economic Buyer**: [Role controlling budget]
- **Technical Evaluator**: [Role validating solution]
- **Potential Champion**: [Role most aligned with our value]

**Implication**
One sentence on how to navigate this structure strategically.

---

## 🎯 Market Position

### Competitive Landscape

| Competitor | Positioning | Notes |
|------------|-------------|-------|
| [Competitor] | [Summary] | [Why relevant] |

### Differentiation
What makes {company_name} stand out:
- [Point 1]
- [Point 2]

### Market Trajectory
- **Stage**: [Growing / Stable / Declining / Pivoting]
- **Evidence**: [Signals justifying assessment]

---

## ⚡ Why This Company Now

### Trigger Events

| Event | Type | Opportunity Signal |
|-------|------|--------------------|
| [Event] | 💰 Funding / 🚀 Product / 👥 Leadership | [Why this matters commercially] |

### Timing Analysis
- **Urgency**: 🟢 High / 🟡 Medium / 🔴 Low
- **Window**: [Is this time-sensitive?]
- **Budget Cycle Clues**: [If any]

### External Pressures
Factors shaping their decisions:
- [Industry trend]
- [Regulatory shift]
- [Competitive challenge]

---

## 🎯 Sales Opportunity

### Pain Points We Can Solve

| Pain Point | Evidence | How We Help |
|------------|----------|-------------|
| [Pain] | [Signal or indicator] | [Relevant value proposition] |

Focus on pains that align *directly* with what you sell.

### Entry Strategy

**Primary Entry Angle**
- [Which role/team to target first and why]

**Rationale**
Tie directly to research signals.

**Alternative Angle**
- [If primary path is blocked]

### Relevant Use Cases
List 2–3 concrete use cases tied to their world, not generic examples:
- [Use case 1]
- [Use case 2]

---

## ⚠️ Risks & Red Flags

### Competitive Threats
- [Existing vendor footprint]
- [Signs of strong competitor presence]

### Fit Concerns
- [Size or complexity mismatch]
- [Potential misalignment]

### Research Red Flags
- [Signals that require validation]

---

## ❓ Questions to Validate in First Contact

1. [Question confirming their current situation]
2. [Question exploring implied challenge]
3. [Question about their priorities/timeline]
4. [Question about decision dynamics]
5. [Question about success criteria]

These are *validation questions*, not discovery questions.

---

## 📚 Relevant References

{"From your knowledge base:" if kb_chunks else "No matches found in your knowledge base."}

| Document | Relevance |
|----------|-----------|
{kb_references}

---

## 📊 Research Confidence & Gaps

| Source | Status | Notes |
|--------|--------|-------|
| Claude Web Search | {claude_status} | [Quality] |
| Google Search | {gemini_status} | [Quality] |
| Chamber of Commerce | {kvk_status} | [If applicable] |
| Website Scrape | {website_status} | [If used] |
| Knowledge Base | {kb_status} | [Matches found] |

### Information Gaps
List what could not be verified and must be confirmed in conversation.

---

RULES:
- Be precise, commercially relevant and context-aware.
- Anchor all insights in real evidence; never guess.
- Write for a senior sales professional who needs intelligence, not volume.
- Keep the brief under 1200 words (excluding tables).
- This is **company intelligence**, not meeting preparation.
- If something is unclear, label it as "Unverified" rather than speculating.
- Prioritize official sources (Chamber of Commerce, company website) over inferred data.

{lang_instruction}

Generate the complete research brief now:"""

        try:
            # Use await since claude.client is now AsyncAnthropic
            response = await self.claude.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.2,
                messages=[{
                    "role": "user",
                    "content": merge_prompt
                }]
            )
            
            return response.content[0].text
            
        except Exception as e:
            # Fallback: just concatenate the sources
            logger.error(f"Error generating unified brief: {e}")
            return f"# Research Brief: {company_name}\n\n" + "\n\n---\n\n".join(source_data)
