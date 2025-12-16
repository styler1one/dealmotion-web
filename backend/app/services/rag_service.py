"""
RAG Service for Meeting Preparation

Retrieves relevant context from Knowledge Base (Pinecone) and Research Briefs
to build comprehensive meeting preparation context.

Enhanced with Profile Context for personalized outputs.
"""

from typing import List, Dict, Any, Optional
import logging
from app.database import get_supabase_service

logger = logging.getLogger(__name__)

# Lazy initialization to avoid import errors
_embeddings_service = None
_vector_store = None
_context_service = None

def get_embeddings_service():
    global _embeddings_service
    if _embeddings_service is None:
        from app.services.embeddings import EmbeddingsService
        _embeddings_service = EmbeddingsService()
    return _embeddings_service

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        from app.services.vector_store import VectorStore
        _vector_store = VectorStore()
    return _vector_store

def get_context_service():
    global _context_service
    if _context_service is None:
        from app.services.context_service import ContextService
        _context_service = ContextService()
    return _context_service


class RAGService:
    """Service for Retrieval-Augmented Generation queries"""
    
    def __init__(self):
        self.supabase = get_supabase_service()
    
    async def query_knowledge_base(
        self,
        query: str,
        organization_id: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query Knowledge Base (Pinecone) for relevant chunks
        
        Args:
            query: Search query (company name + context)
            organization_id: Filter by organization
            top_k: Number of results to return
            
        Returns:
            List of relevant KB chunks with metadata
        """
        try:
            # Generate embedding for query
            query_embedding = await get_embeddings_service().embed_text(query)
            
            # Query Pinecone with organization filter
            matches = get_vector_store().query_vectors(
                query_vector=query_embedding,
                filter={"organization_id": organization_id},
                top_k=top_k,
                include_metadata=True
            )
            
            # Extract and format results
            kb_chunks = []
            for match in matches:
                kb_chunks.append({
                    "text": match.metadata.get("text", ""),
                    "source": match.metadata.get("filename", "Unknown"),
                    "score": match.score,
                    "chunk_id": match.id
                })
            
            logger.info(f"Found {len(kb_chunks)} KB chunks for query: {query[:50]}...")
            return kb_chunks
            
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return []
    
    async def query_research_brief(
        self,
        company_name: str,
        organization_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing research brief for company.
        
        Uses exact matching to prevent cross-prospect data leakage.
        
        Args:
            company_name: Prospect company name
            organization_id: Filter by organization
            
        Returns:
            Research brief data if found, None otherwise
        """
        try:
            # First try exact match (case-sensitive)
            response = self.supabase.table("research_briefs").select(
                "id, company_name, brief_content, created_at"
            ).eq(
                "organization_id", organization_id
            ).eq(
                "company_name", company_name
            ).eq(
                "status", "completed"
            ).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                research = response.data[0]
                logger.info(f"Found research brief for {company_name} (exact match)")
                return research
            
            # Fallback: case-insensitive exact match
            response = self.supabase.table("research_briefs").select(
                "id, company_name, brief_content, created_at"
            ).eq(
                "organization_id", organization_id
            ).ilike(
                "company_name", company_name
            ).eq(
                "status", "completed"
            ).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                research = response.data[0]
                logger.info(f"Found research brief for {company_name} (case-insensitive)")
                return research
            
            logger.info(f"No research brief found for {company_name}")
            return None
                
        except Exception as e:
            logger.error(f"Error querying research brief: {e}")
            return None
    
    async def combine_results(
        self,
        kb_chunks: List[Dict[str, Any]],
        research_data: Optional[Dict[str, Any]],
        prospect_company: str,
        meeting_type: str,
        custom_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Combine KB and Research data into structured context
        
        Args:
            kb_chunks: Knowledge Base chunks
            research_data: Research brief data
            prospect_company: Prospect company name
            meeting_type: Type of meeting
            custom_notes: Optional custom notes
            
        Returns:
            Structured context for AI generation
        """
        # Build company context from KB
        company_context = self._format_kb_chunks(kb_chunks)
        
        # Build prospect context from research
        prospect_context = self._format_research_data(research_data) if research_data else None
        
        # Combine into final context
        context = {
            "prospect_company": prospect_company,
            "meeting_type": meeting_type,
            "custom_notes": custom_notes or "",
            "company_info": {
                "kb_chunks": kb_chunks,
                "formatted_context": company_context
            },
            "prospect_info": {
                "research_data": research_data,
                "formatted_context": prospect_context
            },
            "has_kb_data": len(kb_chunks) > 0,
            "has_research_data": research_data is not None
        }
        
        logger.info(
            f"Combined context: {len(kb_chunks)} KB chunks, "
            f"{'with' if research_data else 'without'} research data"
        )
        
        return context
    
    def _format_kb_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Format KB chunks into readable text"""
        if not chunks:
            return "No company knowledge base data available."
        
        formatted = "## Your Company Information (from Knowledge Base):\n\n"
        for i, chunk in enumerate(chunks[:10], 1):  # Limit to top 10
            formatted += f"{i}. **{chunk['source']}** (relevance: {chunk['score']:.2f})\n"
            formatted += f"   {chunk['text'][:300]}...\n\n"
        
        return formatted
    
    def _format_research_data(self, research: Dict[str, Any]) -> str:
        """Format research data into readable text"""
        formatted = f"## Prospect Intelligence (from Research):\n\n"
        formatted += f"**Company**: {research.get('company_name', 'Unknown')}\n\n"
        
        if research.get('brief_content'):
            # Include FULL research brief - it contains critical BANT signals, 
            # leadership team, entry strategy, and timing assessment
            # Don't truncate as this intelligence is essential for preparation
            brief_content = research['brief_content']
            
            # Only truncate if extremely long (> 6000 chars)
            if len(brief_content) > 6000:
                formatted += f"**Research Brief**:\n{brief_content[:6000]}\n\n[Research continues...]\n\n"
            else:
                formatted += f"**Research Brief**:\n{brief_content}\n\n"
        
        return formatted
    
    async def query_meeting_history(
        self,
        organization_id: str,
        prospect_id: Optional[str] = None,
        prospect_company_name: Optional[str] = None,
        selected_followup_ids: Optional[List[str]] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Query previous meeting followups for a prospect
        
        Args:
            organization_id: Organization ID
            prospect_id: Prospect ID (preferred lookup)
            prospect_company_name: Fallback company name lookup
            selected_followup_ids: Specific followup IDs to include (user selection)
            limit: Maximum number of followups to return
            
        Returns:
            List of previous followup data with summaries and key outcomes
        """
        try:
            followups = []
            
            # If specific followups are selected, fetch those
            if selected_followup_ids and len(selected_followup_ids) > 0:
                result = self.supabase.table("followups").select(
                    "id, meeting_date, meeting_subject, executive_summary, "
                    "prospect_company_name, status, created_at"
                ).eq("organization_id", organization_id).in_("id", selected_followup_ids).order("meeting_date", desc=True).execute()
                
                if result.data:
                    followups = result.data
                    logger.info(f"Found {len(followups)} selected followups for meeting history")
            
            # Otherwise, auto-fetch recent followups for this prospect
            else:
                query = self.supabase.table("followups").select(
                    "id, meeting_date, meeting_subject, executive_summary, "
                    "prospect_company_name, status, created_at"
                ).eq("organization_id", organization_id).eq("status", "completed")
                
                # Try prospect_id first, then company name
                if prospect_id:
                    query = query.eq("prospect_id", prospect_id)
                elif prospect_company_name:
                    query = query.ilike("prospect_company_name", prospect_company_name)
                else:
                    return []
                
                result = query.order("meeting_date", desc=True).limit(limit).execute()
                
                if result.data:
                    followups = result.data
                    logger.info(f"Found {len(followups)} recent followups for meeting history")
            
            return followups
            
        except Exception as e:
            logger.error(f"Error querying meeting history: {e}")
            return []
    
    def _format_meeting_history(self, followups: List[Dict[str, Any]]) -> str:
        """Format previous meeting followups into readable context"""
        if not followups:
            return ""
        
        formatted = "## Previous Meeting History\n\n"
        formatted += "**IMPORTANT**: Use this context to:\n"
        formatted += "- Reference specific points from previous conversations\n"
        formatted += "- Follow up on open action items and commitments\n"
        formatted += "- Build on established rapport and understanding\n"
        formatted += "- Avoid repeating questions already answered\n\n"
        
        for i, followup in enumerate(followups, 1):
            meeting_date = followup.get("meeting_date", "Unknown date")
            if meeting_date and meeting_date != "Unknown date":
                # Format date nicely
                try:
                    from datetime import datetime
                    if isinstance(meeting_date, str):
                        dt = datetime.fromisoformat(meeting_date.replace("Z", "+00:00"))
                        meeting_date = dt.strftime("%d %B %Y")
                except:
                    pass
            
            formatted += f"### Meeting {i}: {meeting_date}\n"
            formatted += f"**Subject**: {followup.get('meeting_subject', 'Not specified')}\n\n"
            
            summary = followup.get("executive_summary", "")
            if summary:
                # Limit summary length but keep substantial
                if len(summary) > 2000:
                    summary = summary[:2000] + "\n\n[Summary continues...]"
                formatted += f"**Summary**:\n{summary}\n\n"
            else:
                formatted += "*No summary available for this meeting.*\n\n"
            
            formatted += "---\n\n"
        
        return formatted
    
    async def build_context_for_ai(
        self,
        prospect_company: str,
        meeting_type: str,
        organization_id: str,
        user_id: Optional[str] = None,
        custom_notes: Optional[str] = None,
        prospect_id: Optional[str] = None,
        selected_followup_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Main method to build complete context for AI generation
        
        Args:
            prospect_company: Prospect company name
            meeting_type: Type of meeting
            organization_id: Organization ID
            user_id: Optional user ID for profile context
            custom_notes: Optional custom notes
            prospect_id: Optional prospect ID for better matching
            selected_followup_ids: Optional list of followup IDs to include from meeting history
            
        Returns:
            Complete context for AI prompt
        """
        # Build search query
        query = f"{prospect_company} {meeting_type} meeting"
        if custom_notes:
            query += f" {custom_notes}"
        
        # Query KB and Research in parallel
        kb_chunks = await self.query_knowledge_base(query, organization_id)
        research_data = await self.query_research_brief(prospect_company, organization_id)
        
        # Query meeting history (previous conversations)
        meeting_history = await self.query_meeting_history(
            organization_id=organization_id,
            prospect_id=prospect_id,
            prospect_company_name=prospect_company,
            selected_followup_ids=selected_followup_ids
        )
        
        # Combine results
        context = await self.combine_results(
            kb_chunks,
            research_data,
            prospect_company,
            meeting_type,
            custom_notes
        )
        
        # Add meeting history context
        if meeting_history:
            context["meeting_history"] = meeting_history
            context["has_meeting_history"] = True
            context["formatted_meeting_history"] = self._format_meeting_history(meeting_history)
            logger.info(f"Added {len(meeting_history)} previous meetings to context")
        else:
            context["meeting_history"] = []
            context["has_meeting_history"] = False
            context["formatted_meeting_history"] = ""
        
        # Add profile context if user_id provided
        if user_id:
            try:
                ctx_service = get_context_service()
                profile_context = ctx_service.get_user_context(user_id, organization_id)
                context["profile_context"] = profile_context
                context["has_profile_context"] = True
                
                # Add formatted profile context for prompt
                formatted_profile = ctx_service.get_context_for_prompt(
                    user_id, organization_id, max_tokens=1500
                )
                context["formatted_profile_context"] = formatted_profile
                
                logger.info(f"Added profile context for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not load profile context: {e}")
                context["has_profile_context"] = False
                context["formatted_profile_context"] = ""
        else:
            context["has_profile_context"] = False
            context["formatted_profile_context"] = ""
        
        return context


# Singleton instance
rag_service = RAGService()
