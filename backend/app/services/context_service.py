"""
Context Service - Unified context API for AI agents
Provides sales profile + company profile + KB summary
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from supabase import Client
from app.database import get_supabase_service
import json


class ContextService:
    """Service for providing unified context to AI agents."""
    
    def __init__(self):
        """Initialize Supabase client and cache using centralized module."""
        self.client: Client = get_supabase_service()
        
        # Simple in-memory cache (in production, use Redis)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(hours=1)
    
    def get_user_context(
        self,
        user_id: str,
        organization_id: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete user context for AI agents.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            use_cache: Whether to use cached context
            
        Returns:
            Dict with sales_profile, company_profile, and kb_summary
        """
        cache_key = f"{user_id}:{organization_id}"
        
        # Check cache
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() < cached["expires_at"]:
                print(f"DEBUG: Using cached context for {cache_key}")
                return cached["data"]
        
        # Build context
        context = {
            "sales_profile": self._get_sales_profile(user_id),
            "company_profile": self._get_company_profile(organization_id),
            "kb_summary": self._get_kb_summary(organization_id)
        }
        
        # Cache it
        self._cache[cache_key] = {
            "data": context,
            "expires_at": datetime.now() + self._cache_ttl
        }
        
        return context
    
    def get_context_for_prompt(
        self,
        user_id: str,
        organization_id: str,
        max_tokens: int = 2000
    ) -> str:
        """
        Get context formatted for AI prompt injection.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            max_tokens: Max tokens to use (rough estimate)
            
        Returns:
            Formatted context string for AI prompt
        """
        context = self.get_user_context(user_id, organization_id)
        
        # Build formatted context
        formatted = self._format_context_for_prompt(context, max_tokens)
        
        return formatted
    
    def invalidate_cache(self, user_id: str, organization_id: str):
        """
        Invalidate cached context for user.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
        """
        cache_key = f"{user_id}:{organization_id}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            print(f"DEBUG: Invalidated cache for {cache_key}")
    
    # ==========================================
    # Private Methods
    # ==========================================
    
    def _get_sales_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get sales profile for user."""
        try:
            response = self.client.table("sales_profiles")\
                .select("*")\
                .eq("user_id", user_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get sales profile: {str(e)}")
            return None
    
    def _get_company_profile(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get company profile for organization."""
        try:
            response = self.client.table("company_profiles")\
                .select("*")\
                .eq("organization_id", organization_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get company profile: {str(e)}")
            return None
    
    def _get_kb_summary(self, organization_id: str) -> Dict[str, Any]:
        """Get knowledge base summary for organization."""
        try:
            # Get KB file count
            response = self.client.table("knowledge_base_files")\
                .select("id, filename, status", count="exact")\
                .eq("organization_id", organization_id)\
                .eq("status", "completed")\
                .execute()
            
            total_files = len(response.data) if response.data else 0
            
            # Get chunk count
            chunk_response = self.client.table("knowledge_base_chunks")\
                .select("id", count="exact")\
                .eq("organization_id", organization_id)\
                .execute()
            
            total_chunks = len(chunk_response.data) if chunk_response.data else 0
            
            return {
                "total_documents": total_files,
                "total_chunks": total_chunks,
                "has_knowledge_base": total_files > 0
            }
            
        except Exception as e:
            print(f"ERROR: Failed to get KB summary: {str(e)}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "has_knowledge_base": False
            }
    
    def _format_context_for_prompt(
        self,
        context: Dict[str, Any],
        max_tokens: int
    ) -> str:
        """
        Format context for AI prompt injection.
        
        Args:
            context: Full context dict
            max_tokens: Max tokens (rough estimate, 4 chars = 1 token)
            
        Returns:
            Formatted context string
        """
        sales = context.get("sales_profile")
        company = context.get("company_profile")
        kb = context.get("kb_summary", {})
        
        # Build context sections
        sections = []
        
        # Sales Profile Section
        if sales:
            # If there's a sales narrative, use it as the primary context (more personal)
            if sales.get('sales_narrative'):
                sales_section = f"""ABOUT THE SALES REP:
{sales.get('sales_narrative')}

KEY DETAILS:
- Name: {sales.get('full_name', 'N/A')}
- Role: {sales.get('role', 'N/A')}
- Experience: {sales.get('experience_years', 'N/A')} years
- Methodology: {sales.get('sales_methodology', 'N/A')}
- Communication Style: {sales.get('communication_style', 'N/A')}
- Strengths: {', '.join(sales.get('strengths', []))}
- Target Industries: {', '.join(sales.get('target_industries', []))}"""
            else:
                # Fallback to structured format if no narrative
                sales_section = f"""SALES REP CONTEXT:
- Name: {sales.get('full_name', 'N/A')}
- Role: {sales.get('role', 'N/A')}
- Experience: {sales.get('experience_years', 'N/A')} years
- Methodology: {sales.get('sales_methodology', 'N/A')}
- Communication Style: {sales.get('communication_style', 'N/A')}
- Strengths: {', '.join(sales.get('strengths', []))}
- Target Industries: {', '.join(sales.get('target_industries', []))}
- Target Regions: {', '.join(sales.get('target_regions', []))}
- Quarterly Goals: {sales.get('quarterly_goals', 'N/A')}"""
            
                if sales.get('ai_summary'):
                    sales_section += f"\n- AI Summary: {sales['ai_summary']}"
            
            sections.append(sales_section)
        
        # Company Profile Section
        if company:
            # If there's a company narrative, use it as the primary context (more compelling)
            if company.get('company_narrative'):
                company_section = f"""ABOUT THE COMPANY:
{company.get('company_narrative')}

KEY DETAILS:
- Company: {company.get('company_name', 'N/A')}
- Industry: {company.get('industry', 'N/A')}"""
                
                # Add products summary
                products = company.get('products', [])
                if products:
                    company_section += "\n- Products:"
                    for p in products[:3]:
                        company_section += f"\n  • {p.get('name', 'N/A')}: {p.get('value_proposition', 'N/A')}"
                
                # Add differentiators
                differentiators = company.get('differentiators', [])
                if differentiators:
                    company_section += f"\n- Key Differentiators: {', '.join(differentiators[:5])}"
            else:
                # Fallback to structured format if no narrative
                company_section = f"""COMPANY CONTEXT:
- Company: {company.get('company_name', 'N/A')}
- Industry: {company.get('industry', 'N/A')}"""
                
                # Products
                products = company.get('products', [])
                if products:
                    company_section += "\n- Products:"
                    for p in products[:3]:  # Limit to 3 products
                        company_section += f"\n  • {p.get('name', 'N/A')}: {p.get('value_proposition', 'N/A')}"
                
                # Value Props
                value_props = company.get('core_value_props', [])
                if value_props:
                    company_section += f"\n- Value Propositions: {', '.join(value_props[:5])}"
                
                # ICP
                icp = company.get('ideal_customer_profile', {})
                if icp:
                    if icp.get('industries'):
                        company_section += f"\n- Target Industries: {', '.join(icp['industries'][:5])}"
                    if icp.get('company_sizes'):
                        company_section += f"\n- Target Company Sizes: {', '.join(icp['company_sizes'])}"
                
                # Case Studies
                case_studies = company.get('case_studies', [])
                if case_studies:
                    company_section += f"\n- Case Studies: {len(case_studies)} available"
                
                if company.get('ai_summary'):
                    company_section += f"\n- AI Summary: {company['ai_summary']}"
            
            sections.append(company_section)
        
        # Knowledge Base Section
        if kb.get('has_knowledge_base'):
            kb_section = f"""KNOWLEDGE BASE:
- Documents: {kb.get('total_documents', 0)} files uploaded
- Chunks: {kb.get('total_chunks', 0)} searchable chunks
- Status: Available for RAG queries"""
            sections.append(kb_section)
        
        # Combine sections
        full_context = "\n\n".join(sections)
        
        # Truncate if too long (rough estimate: 4 chars = 1 token)
        max_chars = max_tokens * 4
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "..."
        
        return full_context
    
    def get_context_summary(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get a summary of available context.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            
        Returns:
            Summary dict with availability flags
        """
        context = self.get_user_context(user_id, organization_id)
        
        return {
            "has_sales_profile": context.get("sales_profile") is not None,
            "sales_profile_completeness": context.get("sales_profile", {}).get("profile_completeness", 0),
            "has_company_profile": context.get("company_profile") is not None,
            "company_profile_completeness": context.get("company_profile", {}).get("profile_completeness", 0),
            "has_knowledge_base": context.get("kb_summary", {}).get("has_knowledge_base", False),
            "kb_document_count": context.get("kb_summary", {}).get("total_documents", 0),
            "context_quality": self._calculate_context_quality(context)
        }
    
    def _calculate_context_quality(self, context: Dict[str, Any]) -> str:
        """
        Calculate overall context quality.
        
        Args:
            context: Full context dict
            
        Returns:
            Quality rating: 'excellent', 'good', 'fair', 'poor'
        """
        score = 0
        
        # Sales profile (40 points)
        sales = context.get("sales_profile")
        if sales:
            score += sales.get("profile_completeness", 0) * 0.4
        
        # Company profile (40 points)
        company = context.get("company_profile")
        if company:
            score += company.get("profile_completeness", 0) * 0.4
        
        # Knowledge base (20 points)
        kb = context.get("kb_summary", {})
        if kb.get("has_knowledge_base"):
            score += 20
        
        # Rate quality
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        else:
            return "poor"
