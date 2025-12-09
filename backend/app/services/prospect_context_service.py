"""
Prospect Context Service - Unified context aggregation for AI agents

This service provides a single source of truth for all context related to 
a specific prospect, combining:
- Sales Profile (narrative + details)
- Company Profile (narrative + details)
- Research Brief (company data, key people, news)
- Meeting Preparations (briefs, talking points, questions)
- Previous Follow-ups (summaries, action items)
- Knowledge Base chunks (relevant documents)

This ensures maximum context is available for AI to generate the best outputs.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import Client
from app.database import get_supabase_service
from app.services.seller_context_builder import get_seller_context_builder

logger = logging.getLogger(__name__)


class ProspectContextService:
    """
    Unified service for aggregating all context for a specific prospect.
    
    This solves the problem of fragmented context by providing a single
    method to get ALL relevant information for AI prompts.
    """
    
    def __init__(self):
        """Initialize Supabase client using centralized module."""
        self.client: Client = get_supabase_service()
        
        # Cache for expensive queries (in production, use Redis)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=30)
    
    async def get_full_prospect_context(
        self,
        prospect_company: str,
        organization_id: str,
        user_id: str,
        meeting_prep_id: Optional[str] = None,
        include_kb: bool = True,
        max_kb_chunks: int = 5
    ) -> Dict[str, Any]:
        """
        Get complete context for a prospect, aggregating all available data.
        
        Args:
            prospect_company: Name of the prospect company
            organization_id: Organization ID
            user_id: User ID for profile context
            meeting_prep_id: Optional specific meeting prep to include
            include_kb: Whether to search Knowledge Base
            max_kb_chunks: Maximum KB chunks to retrieve
            
        Returns:
            Complete context dict with all available information
        """
        context = {
            "prospect_company": prospect_company,
            "retrieved_at": datetime.utcnow().isoformat(),
            
            # Profile context
            "sales_profile": None,
            "company_profile": None,
            
            # Prospect-specific context
            "research": None,
            "meeting_preps": [],
            "previous_followups": [],
            
            # Knowledge context
            "kb_chunks": [],
            
            # Metadata
            "context_completeness": 0,
            "available_sources": []
        }
        
        # 1. Get Sales Profile
        sales_profile = self._get_sales_profile(user_id)
        if sales_profile:
            context["sales_profile"] = sales_profile
            context["available_sources"].append("sales_profile")
        
        # 2. Get Company Profile
        company_profile = self._get_company_profile(organization_id)
        if company_profile:
            context["company_profile"] = company_profile
            context["available_sources"].append("company_profile")
        
        # 3. Get Research Brief for this prospect
        research = self._get_research_brief(prospect_company, organization_id)
        if research:
            context["research"] = research
            context["available_sources"].append("research")
        
        # 4. Get Meeting Preps for this prospect
        meeting_preps = self._get_meeting_preps(
            prospect_company, 
            organization_id,
            specific_prep_id=meeting_prep_id
        )
        if meeting_preps:
            context["meeting_preps"] = meeting_preps
            context["available_sources"].append("meeting_preps")
        
        # 5. Get Previous Follow-ups for this prospect
        followups = self._get_previous_followups(prospect_company, organization_id)
        if followups:
            context["previous_followups"] = followups
            context["available_sources"].append("previous_followups")
        
        # 6. Get relevant KB chunks
        if include_kb:
            kb_chunks = await self._get_relevant_kb_chunks(
                prospect_company,
                organization_id,
                max_chunks=max_kb_chunks
            )
            if kb_chunks:
                context["kb_chunks"] = kb_chunks
                context["available_sources"].append("knowledge_base")
        
        # Calculate context completeness
        context["context_completeness"] = self._calculate_completeness(context)
        
        logger.info(
            f"Built prospect context for {prospect_company}: "
            f"{len(context['available_sources'])} sources, "
            f"{context['context_completeness']}% complete"
        )
        
        return context
    
    def format_context_for_prompt(
        self,
        context: Dict[str, Any],
        max_tokens: int = 4000,
        focus: str = "general",  # "general", "followup", "preparation"
        include_style_rules: bool = True
    ) -> str:
        """
        Format the full context into a string suitable for AI prompt injection.
        
        Args:
            context: Full context dict from get_full_prospect_context
            max_tokens: Maximum tokens to use (rough estimate)
            focus: What to prioritize in the context
            include_style_rules: Whether to include output style rules
            
        Returns:
            Formatted context string for AI prompt
        """
        sections = []
        
        # 1. Sales Profile - Always include narrative if available
        if context.get("sales_profile"):
            sales = context["sales_profile"]
            if sales.get("sales_narrative"):
                sections.append(f"""## ABOUT YOU (THE SALES REP):
{sales['sales_narrative']}

Key Details:
- Name: {sales.get('full_name', 'N/A')}
- Experience: {sales.get('years_experience', 'N/A')} years
- Sales Methodology: {sales.get('sales_methodology', 'N/A')}
- Communication Style: {sales.get('communication_style', 'N/A')}""")
            else:
                sections.append(f"""## ABOUT YOU (THE SALES REP):
- Name: {sales.get('full_name', 'N/A')}
- Role: {sales.get('job_title', 'N/A')}
- Experience: {sales.get('years_experience', 'N/A')} years
- Sales Style: {sales.get('sales_methodology', 'N/A')}""")
            
            # Add style rules if requested - use centralized SellerContextBuilder
            if include_style_rules:
                seller_builder = get_seller_context_builder()
                style_guide = seller_builder.get_style_guide(sales)
                sections.append(seller_builder.get_output_style_rules(style_guide))
        
        # 2. Company Profile - Your company context
        if context.get("company_profile"):
            company = context["company_profile"]
            # Extract products from products array
            products = [p.get('name') for p in (company.get('products', []) or []) if isinstance(p, dict) and p.get('name')]
            products_str = ', '.join(products[:5]) if products else 'N/A'
            # Extract value propositions from core_value_props
            value_props = company.get('core_value_props', []) or []
            value_props_str = ', '.join(value_props[:3]) if value_props else 'N/A'
            
            if company.get("company_narrative"):
                sections.append(f"""## YOUR COMPANY:
{company['company_narrative']}

Products/Services: {products_str}
Value Propositions: {value_props_str}""")
            else:
                sections.append(f"""## YOUR COMPANY:
- Company: {company.get('company_name', 'N/A')}
- Industry: {company.get('industry', 'N/A')}
- Products: {products_str}""")
        
        # 3. Research Data - Prospect intelligence
        if context.get("research"):
            research = context["research"]
            # Use FULL brief_content - contains BANT signals, leadership, entry strategy
            brief_content = research.get('brief_content', 'No research available')
            # Only truncate if extremely long
            if len(brief_content) > 5000:
                brief_content = brief_content[:5000] + "\n\n[Research continues with additional insights...]"
            sections.append(f"""## PROSPECT RESEARCH ({context['prospect_company']}):
{brief_content}""")
        
        # 4. Meeting Prep Context - What was prepared
        if context.get("meeting_preps") and focus in ["followup", "general"]:
            # Get the most relevant prep (latest or specific)
            prep = context["meeting_preps"][0]
            sections.append(f"""## MEETING PREPARATION (What you prepared):
**Meeting Type:** {prep.get('meeting_type', 'N/A')}

**Key Talking Points:**
{self._format_list(prep.get('talking_points', []))}

**Questions to Ask:**
{self._format_list(prep.get('questions', []))}

**Strategy:**
{prep.get('strategy', 'No strategy recorded')[:500]}""")
        
        # 5. Previous Follow-ups - What happened before
        if context.get("previous_followups") and focus in ["followup", "general"]:
            followup = context["previous_followups"][0]  # Most recent
            if followup.get("executive_summary"):
                sections.append(f"""## PREVIOUS MEETING SUMMARY:
{followup.get('executive_summary', '')}

**Decisions Made:**
{self._format_list(followup.get('decisions', []))}

**Open Action Items:**
{self._format_list([item.get('task', '') for item in followup.get('action_items', []) if not item.get('completed')])}""")
        
        # 6. Knowledge Base - Relevant company documents
        if context.get("kb_chunks"):
            kb_text = "\n".join([
                f"- {chunk.get('source', 'Document')}: {chunk.get('text', '')[:200]}..."
                for chunk in context["kb_chunks"][:3]
            ])
            sections.append(f"""## RELEVANT COMPANY KNOWLEDGE:
{kb_text}""")
        
        # Combine sections
        full_context = "\n\n".join(sections)
        
        # Truncate if too long
        max_chars = max_tokens * 4
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "\n\n[Context truncated for length]"
        
        return full_context
    
    # ==========================================
    # Private Methods
    # ==========================================
    
    def _get_sales_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get sales profile for user."""
        try:
            response = self.client.table("sales_profiles")\
                .select("*")\
                .eq("user_id", user_id)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting sales profile: {e}")
            return None
    
    def _get_company_profile(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get company profile for organization."""
        try:
            response = self.client.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting company profile: {e}")
            return None
    
    def _get_research_brief(
        self, 
        prospect_company: str, 
        organization_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get research brief for prospect company.
        
        Uses exact match first, then case-insensitive exact match.
        No fuzzy matching to prevent cross-prospect data leakage.
        """
        try:
            # First try exact match (case-sensitive)
            response = self.client.table("research_briefs")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .eq("company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            
            # Fallback: case-insensitive exact match
            response = self.client.table("research_briefs")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .ilike("company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error getting research brief: {e}")
            return None
    
    def _get_meeting_preps(
        self,
        prospect_company: str,
        organization_id: str,
        specific_prep_id: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get meeting preps for prospect company.
        
        If specific_prep_id is provided, uses that (most reliable).
        Otherwise uses exact name matching to prevent cross-prospect leakage.
        """
        try:
            # If we have a specific prep ID, use that (most accurate)
            if specific_prep_id:
                response = self.client.table("meeting_preps")\
                    .select("*")\
                    .eq("id", specific_prep_id)\
                    .eq("organization_id", organization_id)\
                    .execute()
                return response.data or []
            
            # Otherwise, try exact match first
            response = self.client.table("meeting_preps")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .eq("prospect_company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            if response.data:
                return response.data
            
            # Fallback: case-insensitive exact match
            response = self.client.table("meeting_preps")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .ilike("prospect_company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting meeting preps: {e}")
            return []
    
    def _get_previous_followups(
        self,
        prospect_company: str,
        organization_id: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get previous follow-ups for prospect company.
        
        Uses exact name matching to prevent cross-prospect data leakage.
        """
        try:
            # First try exact match
            response = self.client.table("followups")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .eq("prospect_company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            if response.data:
                return response.data
            
            # Fallback: case-insensitive exact match
            response = self.client.table("followups")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .ilike("prospect_company_name", prospect_company)\
                .eq("status", "completed")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting previous followups: {e}")
            return []
    
    async def _get_relevant_kb_chunks(
        self,
        prospect_company: str,
        organization_id: str,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """Get relevant KB chunks for the prospect context."""
        try:
            # Lazy import to avoid circular imports
            from app.services.embeddings import EmbeddingsService
            from app.services.vector_store import VectorStore
            
            embeddings = EmbeddingsService()
            vector_store = VectorStore()
            
            # Search for case studies and relevant product info
            query = f"{prospect_company} case study success story product solution"
            query_embedding = await embeddings.embed_text(query)
            
            matches = vector_store.query_vectors(
                query_vector=query_embedding,
                filter={"organization_id": organization_id},
                top_k=max_chunks,
                include_metadata=True
            )
            
            chunks = []
            for match in matches:
                chunks.append({
                    "text": match.metadata.get("text", ""),
                    "source": match.metadata.get("filename", "Unknown"),
                    "score": match.score
                })
            
            return chunks
        except Exception as e:
            logger.warning(f"Error getting KB chunks: {e}")
            return []
    
    def _calculate_completeness(self, context: Dict[str, Any]) -> int:
        """Calculate context completeness as percentage."""
        score = 0
        max_score = 100
        
        # Sales profile (20 points)
        if context.get("sales_profile"):
            score += 10
            if context["sales_profile"].get("sales_narrative"):
                score += 10
        
        # Company profile (20 points)
        if context.get("company_profile"):
            score += 10
            if context["company_profile"].get("company_narrative"):
                score += 10
        
        # Research (25 points)
        if context.get("research"):
            score += 15
            # Additional points if research has substantial content
            brief_content = context["research"].get("brief_content", "")
            if len(brief_content) > 2000:
                score += 10  # Rich research content
        
        # Meeting preps (20 points)
        if context.get("meeting_preps"):
            score += 20
        
        # KB chunks (15 points)
        if context.get("kb_chunks"):
            score += 15
        
        return min(score, max_score)
    
    def _format_list(self, items: List[Any], max_items: int = 5) -> str:
        """Format a list of items as bullet points."""
        if not items:
            return "- No items"
        
        formatted = []
        for item in items[:max_items]:
            if isinstance(item, dict):
                # Handle dict items (like talking points)
                text = item.get("text", item.get("point", str(item)))
            else:
                text = str(item)
            formatted.append(f"- {text}")
        
        if len(items) > max_items:
            formatted.append(f"- ... and {len(items) - max_items} more")
        
        return "\n".join(formatted)
    
    # NOTE: _derive_style_guide and _format_style_rules have been removed
    # Use SellerContextBuilder from seller_context_builder.py instead
    # This eliminates code duplication - SPEC-033


# Lazy singleton
_prospect_context_service: Optional[ProspectContextService] = None

def get_prospect_context_service() -> ProspectContextService:
    """Get or create prospect context service instance."""
    global _prospect_context_service
    if _prospect_context_service is None:
        _prospect_context_service = ProspectContextService()
    return _prospect_context_service

