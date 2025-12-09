"""
Seller Context Builder - Centralized service for building unified seller context

This service provides a consistent seller context block that gets injected into
ALL AI prompts. It ensures personalized output across the entire application.

SPEC: SPEC-032-Seller-Context-Prompt-Architecture
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from supabase import Client
from app.database import get_supabase_service

logger = logging.getLogger(__name__)


# Style guide defaults
DEFAULT_STYLE_GUIDE = {
    "tone": "professional",
    "formality": "professional",
    "language_style": "business",
    "persuasion_style": "logic",
    "emoji_usage": False,
    "signoff": "Best regards",
    "writing_length": "concise",
    "confidence_score": 0.3  # Very low - no data available
}

# Tone descriptions for prompts
TONE_DESCRIPTIONS = {
    "direct": "Be straightforward, get to the point quickly, avoid unnecessary pleasantries",
    "warm": "Be friendly and personable, show genuine interest, use relatable language",
    "formal": "Be professional and structured, use proper titles, maintain businesslike tone",
    "casual": "Be relaxed and conversational, use informal language, keep it light",
    "professional": "Balance warmth with professionalism, be clear and respectful"
}

# Formality descriptions
FORMALITY_DESCRIPTIONS = {
    "formal": "Use complete sentences, proper grammar, avoid contractions",
    "professional": "Clear and businesslike, contractions OK, focus on clarity",
    "casual": "Relaxed grammar, conversational flow, friendly and approachable"
}


class SellerContextBuilder:
    """
    Centralized service for building consistent seller context 
    that gets injected into all AI prompts.
    
    This ensures:
    1. Consistent seller identity across all AI outputs
    2. Style guide enforcement for personalized tone
    3. Company context always available
    4. Backward compatibility with existing profiles
    """
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = get_supabase_service()
    
    def build_unified_context(
        self,
        user_id: str,
        organization_id: str,
        format: str = "full",  # "full" | "compact" | "minimal"
        include_style_rules: bool = True
    ) -> str:
        """
        Build the unified seller context block.
        
        This is the main method that ALL prompts should use to get seller context.
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            format: Context format - full, compact, or minimal
            include_style_rules: Whether to include output style rules
            
        Returns:
            Formatted string ready for prompt injection.
        """
        # Get profiles
        sales_profile = self._get_sales_profile(user_id)
        company_profile = self._get_company_profile(organization_id)
        
        if not sales_profile and not company_profile:
            return self._get_fallback_context()
        
        # Get style guide (with fallback to defaults)
        style_guide = self.get_style_guide(sales_profile)
        
        # Build context based on format
        if format == "minimal":
            return self._build_minimal_context(sales_profile, company_profile)
        elif format == "compact":
            return self._build_compact_context(sales_profile, company_profile, style_guide, include_style_rules)
        else:  # full
            return self._build_full_context(sales_profile, company_profile, style_guide, include_style_rules)
    
    def get_style_guide(
        self,
        sales_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get style guide from profile, with fallback to derived/default values.
        
        Args:
            sales_profile: Sales profile dict or None
            
        Returns:
            Style guide dict
        """
        if not sales_profile:
            return DEFAULT_STYLE_GUIDE.copy()
        
        # If style_guide exists in profile, use it
        if sales_profile.get("style_guide"):
            return sales_profile["style_guide"]
        
        # Otherwise, derive from existing fields
        return self._derive_style_guide(sales_profile)
    
    def get_output_style_rules(
        self,
        style_guide: Dict[str, Any]
    ) -> str:
        """
        Format style guide into prompt instructions.
        
        Args:
            style_guide: Style guide dict
            
        Returns:
            Formatted style rules for prompt
        """
        tone = style_guide.get("tone", "professional")
        formality = style_guide.get("formality", "professional")
        emoji = style_guide.get("emoji_usage", False)
        length = style_guide.get("writing_length", "concise")
        signoff = style_guide.get("signoff", "Best regards")
        
        emoji_instruction = "Emoji are OK to use" if emoji else "Do NOT use emoji"
        length_instruction = "Keep messages concise and to the point" if length == "concise" else "Provide detailed explanations"
        
        rules = f"""## OUTPUT STYLE RULES

Match this communication style in ALL your output:

- **Tone**: {tone.title()} - {TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS['professional'])}
- **Formality**: {formality.title()} - {FORMALITY_DESCRIPTIONS.get(formality, FORMALITY_DESCRIPTIONS['professional'])}
- **Emoji**: {emoji_instruction}
- **Length**: {length_instruction}
- **Email sign-off**: Use "{signoff}" when ending emails

**CRITICAL**: Your output must sound like the sales rep wrote it themselves.
Not generic AI text - THEIR voice, THEIR style, THEIR personality.
"""
        return rules
    
    def get_seller_identity(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get seller identity info as a dict (for programmatic use).
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            
        Returns:
            Dict with seller identity info
        """
        sales_profile = self._get_sales_profile(user_id)
        company_profile = self._get_company_profile(organization_id)
        style_guide = self.get_style_guide(sales_profile)
        
        return {
            "has_profile": sales_profile is not None,
            "has_company": company_profile is not None,
            "full_name": sales_profile.get("full_name") if sales_profile else None,
            "role": sales_profile.get("role") if sales_profile else None,
            "company_name": company_profile.get("company_name") if company_profile else None,
            "style_guide": style_guide,
            "products_services": self._extract_products(company_profile) if company_profile else [],
            "value_propositions": self._extract_value_props(company_profile) if company_profile else []
        }
    
    # ==========================================
    # Private Methods
    # ==========================================
    
    def _get_sales_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get sales profile from database."""
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
        """Get company profile from database."""
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
    
    def _derive_style_guide(self, sales_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive style guide from existing profile fields.
        Used when style_guide is not explicitly set.
        """
        communication_style = (sales_profile.get("communication_style") or "").lower()
        methodology = (sales_profile.get("sales_methodology") or "").lower()
        
        # Derive tone
        if "direct" in communication_style:
            tone = "direct"
        elif "warm" in communication_style or "relationship" in communication_style:
            tone = "warm"
        elif "formal" in communication_style:
            tone = "formal"
        elif "casual" in communication_style or "informal" in communication_style:
            tone = "casual"
        else:
            tone = "professional"
        
        # Derive persuasion style from methodology
        if "challenger" in methodology or "spin" in methodology:
            persuasion = "logic"
        elif "story" in methodology or "narrative" in methodology:
            persuasion = "story"
        elif "reference" in methodology or "social" in methodology:
            persuasion = "reference"
        else:
            persuasion = "logic"
        
        return {
            "tone": tone,
            "formality": "professional",
            "language_style": "business",
            "persuasion_style": persuasion,
            "emoji_usage": sales_profile.get("uses_emoji", False),
            "signoff": sales_profile.get("email_signoff", "Best regards"),
            "writing_length": sales_profile.get("writing_length_preference", "concise"),
            "confidence_score": 0.5  # Medium confidence - derived
        }
    
    def _build_full_context(
        self,
        sales_profile: Optional[Dict],
        company_profile: Optional[Dict],
        style_guide: Dict,
        include_style_rules: bool
    ) -> str:
        """Build full context block."""
        sections = []
        
        # Identity section
        if sales_profile:
            identity = f"""## YOUR IDENTITY

- **Name**: {sales_profile.get('full_name', 'Sales Professional')}
- **Role**: {sales_profile.get('role', 'Sales Representative')}
- **Experience**: {sales_profile.get('experience_years', 'N/A')} years
- **Sales Methodology**: {sales_profile.get('sales_methodology', 'Consultative Selling')}
- **Strengths**: {', '.join(sales_profile.get('strengths', ['Building relationships'])[:3])}
- **Communication Style**: {sales_profile.get('communication_style', 'Professional')}"""
            
            # Add narrative if available (most valuable)
            if sales_profile.get('sales_narrative'):
                identity += f"\n\n### About You\n{sales_profile['sales_narrative'][:800]}"
            
            sections.append(identity)
        
        # Company section
        if company_profile:
            products = ', '.join(self._extract_products(company_profile)[:5]) or 'Not specified'
            value_props = ', '.join(self._extract_value_props(company_profile)[:3]) or 'Not specified'
            
            company = f"""## YOUR COMPANY

- **Company**: {company_profile.get('company_name', 'Your Company')}
- **Industry**: {company_profile.get('industry', 'Technology')}
- **Products/Services**: {products}
- **Value Propositions**: {value_props}
- **Target Market**: B2B"""
            
            # Add narrative if available
            if company_profile.get('company_narrative'):
                company += f"\n\n### About Your Company\n{company_profile['company_narrative'][:600]}"
            
            sections.append(company)
        
        # Style rules section
        if include_style_rules:
            sections.append(self.get_output_style_rules(style_guide))
        
        return "\n\n".join(sections)
    
    def _build_compact_context(
        self,
        sales_profile: Optional[Dict],
        company_profile: Optional[Dict],
        style_guide: Dict,
        include_style_rules: bool
    ) -> str:
        """Build compact context block (for token-limited prompts)."""
        parts = []
        
        if sales_profile:
            name = sales_profile.get('full_name', 'Sales Rep')
            role = sales_profile.get('role', '')
            company = company_profile.get('company_name', '') if company_profile else ''
            
            parts.append(f"**Seller**: {name}, {role} at {company}")
            parts.append(f"**Style**: {sales_profile.get('communication_style', 'Professional')}, {style_guide.get('tone', 'professional')} tone")
        
        if company_profile:
            products = ', '.join(self._extract_products(company_profile)[:3])
            if products:
                parts.append(f"**Selling**: {products}")
        
        if include_style_rules:
            emoji = "emoji OK" if style_guide.get("emoji_usage") else "no emoji"
            length = style_guide.get("writing_length", "concise")
            parts.append(f"**Output Style**: {style_guide.get('tone', 'professional')}, {length}, {emoji}")
        
        return "## SELLER CONTEXT\n" + "\n".join(parts)
    
    def _build_minimal_context(
        self,
        sales_profile: Optional[Dict],
        company_profile: Optional[Dict]
    ) -> str:
        """Build minimal context (just name and company)."""
        name = sales_profile.get('full_name', 'Sales Rep') if sales_profile else 'Sales Rep'
        company = company_profile.get('company_name', 'Company') if company_profile else 'Company'
        
        return f"Seller: {name} from {company}"
    
    def _extract_products(self, company_profile: Dict[str, Any]) -> List[str]:
        """
        Extract product names from company_profile.products array.
        
        The products field is an array of objects with 'name' field.
        """
        products = company_profile.get("products", []) or []
        return [
            p.get("name") for p in products 
            if isinstance(p, dict) and p.get("name")
        ]
    
    def _extract_value_props(self, company_profile: Dict[str, Any]) -> List[str]:
        """
        Extract value propositions from company_profile.
        
        Combines core_value_props and differentiators.
        """
        value_props = company_profile.get("core_value_props", []) or []
        differentiators = company_profile.get("differentiators", []) or []
        return value_props + differentiators
    
    def _extract_target_industries(self, company_profile: Dict[str, Any]) -> List[str]:
        """
        Extract target industries from ideal_customer_profile.industries.
        """
        icp = company_profile.get("ideal_customer_profile", {}) or {}
        return icp.get("industries", []) or []
    
    def _get_fallback_context(self) -> str:
        """Fallback when no profile data available."""
        return """## SELLER CONTEXT

No seller profile available. Use professional, business-appropriate language.
Focus on being helpful and clear in all communications.
"""


# Lazy singleton
_seller_context_builder: Optional[SellerContextBuilder] = None


def get_seller_context_builder() -> SellerContextBuilder:
    """Get or create seller context builder instance."""
    global _seller_context_builder
    if _seller_context_builder is None:
        _seller_context_builder = SellerContextBuilder()
    return _seller_context_builder

