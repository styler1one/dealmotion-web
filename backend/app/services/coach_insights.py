"""
Coach AI Insights Service

This service provides intelligent insights using Claude AI and pattern analysis.
It generates personalized tips, predictions, and recommendations based on user
behavior and success patterns.

Features:
- Success pattern analysis
- Claude AI insight generation with seller context (SPEC-033)
- Personalized recommendations
- Tip of the day
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import os
from anthropic import AsyncAnthropic  # Use async client to not block event loop

logger = logging.getLogger(__name__)


class InsightType(str, Enum):
    """Types of insights that can be generated."""
    TIP_OF_DAY = "tip_of_day"
    SUCCESS_PATTERN = "success_pattern"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    PREDICTION = "prediction"


class InsightPriority(str, Enum):
    """Priority levels for insights."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoachInsightsService:
    """
    Service for generating AI-powered insights for the coach.
    """
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.anthropic_client = None
        
        # Initialize Claude client if API key available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.anthropic_client = AsyncAnthropic(api_key=api_key)
    
    async def analyze_success_patterns(
        self, 
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Analyze patterns that correlate with successful outcomes.
        
        This looks at:
        - How many contacts are typically added before successful preps
        - Time between research and prep
        - Follow-up action generation rates
        - Deal progression patterns
        
        Returns:
            Dict with success pattern insights.
        """
        try:
            patterns = {
                "contacts_analysis": {},
                "timing_analysis": {},
                "action_analysis": {},
                "overall_score": 0,
                "recommendations": [],
            }
            
            # Analyze contacts per research
            research_result = self.supabase.table("research_briefs") \
                .select("id, prospect_id, status") \
                .eq("organization_id", organization_id) \
                .eq("status", "completed") \
                .execute()
            
            if research_result.data:
                total_research = len(research_result.data)
                research_with_contacts = 0
                total_contacts = 0
                
                for research in research_result.data:
                    prospect_id = research.get("prospect_id")
                    if prospect_id:
                        contacts_result = self.supabase.table("prospect_contacts") \
                            .select("id") \
                            .eq("prospect_id", prospect_id) \
                            .execute()
                        
                        if contacts_result.data:
                            research_with_contacts += 1
                            total_contacts += len(contacts_result.data)
                
                patterns["contacts_analysis"] = {
                    "total_research": total_research,
                    "research_with_contacts": research_with_contacts,
                    "contact_rate": round(research_with_contacts / total_research, 2) if total_research > 0 else 0,
                    "avg_contacts_per_research": round(total_contacts / total_research, 1) if total_research > 0 else 0,
                }
                
                # Generate recommendation based on contacts
                if patterns["contacts_analysis"]["contact_rate"] < 0.5:
                    patterns["recommendations"].append({
                        "type": "contacts",
                        "priority": InsightPriority.HIGH.value,
                        "message": "Adding contacts before creating preparations significantly improves meeting outcomes. Consider adding at least 1-2 key contacts for each research.",
                        "action": "Add contacts to your research briefs",
                    })
            
            # Analyze prep completion
            prep_result = self.supabase.table("meeting_preps") \
                .select("id, status") \
                .eq("organization_id", organization_id) \
                .execute()
            
            if prep_result.data:
                total_preps = len(prep_result.data)
                completed_preps = sum(1 for p in prep_result.data if p.get("status") == "completed")
                
                patterns["timing_analysis"]["total_preps"] = total_preps
                patterns["timing_analysis"]["completed_preps"] = completed_preps
                patterns["timing_analysis"]["completion_rate"] = round(completed_preps / total_preps, 2) if total_preps > 0 else 0
            
            # Analyze follow-up actions
            followup_result = self.supabase.table("followups") \
                .select("id") \
                .eq("organization_id", organization_id) \
                .eq("status", "completed") \
                .execute()
            
            if followup_result.data:
                total_followups = len(followup_result.data)
                followups_with_actions = 0
                total_actions = 0
                
                for followup in followup_result.data:
                    actions_result = self.supabase.table("followup_actions") \
                        .select("id") \
                        .eq("followup_id", followup["id"]) \
                        .execute()
                    
                    if actions_result.data:
                        followups_with_actions += 1
                        total_actions += len(actions_result.data)
                
                patterns["action_analysis"] = {
                    "total_followups": total_followups,
                    "followups_with_actions": followups_with_actions,
                    "action_rate": round(followups_with_actions / total_followups, 2) if total_followups > 0 else 0,
                    "avg_actions_per_followup": round(total_actions / total_followups, 1) if total_followups > 0 else 0,
                }
                
                # Generate recommendation based on actions
                if patterns["action_analysis"]["action_rate"] < 0.3:
                    patterns["recommendations"].append({
                        "type": "actions",
                        "priority": InsightPriority.MEDIUM.value,
                        "message": "Generating follow-up actions helps you stay organized and increases response rates. Try generating a Customer Report after your next meeting.",
                        "action": "Generate follow-up actions",
                    })
            
            # Calculate overall score (0-100)
            score_components = []
            if patterns["contacts_analysis"].get("contact_rate"):
                score_components.append(patterns["contacts_analysis"]["contact_rate"] * 30)
            if patterns["timing_analysis"].get("completion_rate"):
                score_components.append(patterns["timing_analysis"]["completion_rate"] * 30)
            if patterns["action_analysis"].get("action_rate"):
                score_components.append(patterns["action_analysis"]["action_rate"] * 40)
            
            patterns["overall_score"] = round(sum(score_components)) if score_components else 0
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing success patterns: {e}")
            return {
                "error": str(e),
                "overall_score": 0,
                "recommendations": [],
            }
    
    # Curated tips library - used when no AI tip is cached
    CURATED_TIPS = [
        {
            "category": "research",
            "title": "Power of Preparation",
            "content": "Studies show that sales reps who research their prospects for at least 15 minutes before a call are 30% more likely to schedule a follow-up meeting.",
            "icon": "📚",
        },
        {
            "category": "contacts",
            "title": "Multi-Threading Matters",
            "content": "Deals with 3+ contacts in the buying committee close 40% faster. Try adding multiple stakeholders to your prospect research.",
            "icon": "👥",
        },
        {
            "category": "followup",
            "title": "Speed to Lead",
            "content": "Following up within 1 hour of a meeting increases your chances of advancing the deal by 7x compared to waiting 24 hours.",
            "icon": "⚡",
        },
        {
            "category": "preparation",
            "title": "Personalized Openings",
            "content": "Starting with a personalized observation about the prospect's company or recent news creates 3x more engagement than generic introductions.",
            "icon": "🎯",
        },
        {
            "category": "actions",
            "title": "Customer Reports Win",
            "content": "Sharing a professional customer report after meetings increases response rates by 60% compared to simple thank-you emails.",
            "icon": "📊",
        },
        {
            "category": "timing",
            "title": "Best Prep Timing",
            "content": "The sweet spot for preparation is 1-2 days before the meeting. Too early and you forget details, too late and you're rushed.",
            "icon": "⏰",
        },
    ]
    
    async def generate_tip_of_day(
        self, 
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        force_ai: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a personalized tip of the day.
        
        TASK-038: Token optimization - AI tips cached 1x per day.
        
        Flow:
        1. Check database for cached AI tip from today
        2. If cached → return it (no AI call)
        3. If not cached + force_ai → generate new AI tip + cache it
        4. Otherwise → return curated tip (no AI call)
        
        Args:
            user_id: The user ID
            context: Optional context about user's recent activity
            force_ai: If True, generate new AI tip even if curated available
            
        Returns:
            Dict with tip content and metadata.
        """
        today = datetime.now().date().isoformat()
        
        try:
            # Step 1: Check for cached AI tip from today
            cached_tip = await self._get_cached_tip(user_id, today)
            if cached_tip:
                logger.debug(f"Returning cached AI tip for user {user_id}")
                return cached_tip
            
            # Step 2: If force_ai or first time today, try to generate AI tip
            if force_ai and self.anthropic_client and context:
                try:
                    personalized_tip = await self._generate_personalized_tip(context)
                    if personalized_tip:
                        # Cache the AI tip for today
                        await self._cache_tip(user_id, today, personalized_tip)
                        logger.info(f"Generated and cached new AI tip for user {user_id}")
                        return personalized_tip
                except Exception as e:
                    logger.warning(f"AI tip generation failed, using curated: {e}")
            
            # Step 3: Return curated tip (no AI tokens used)
            return self._get_curated_tip(user_id, today)
            
        except Exception as e:
            logger.error(f"Error generating tip of day: {e}")
            # Return a safe default
            return {
                "id": "fallback_0",
                "category": self.CURATED_TIPS[0]["category"],
                "title": self.CURATED_TIPS[0]["title"],
                "content": self.CURATED_TIPS[0]["content"],
                "icon": self.CURATED_TIPS[0]["icon"],
                "is_personalized": False,
            }
    
    async def _get_cached_tip(self, user_id: str, tip_date: str) -> Optional[Dict[str, Any]]:
        """Get cached AI tip from database for today."""
        try:
            result = self.supabase.table("coach_daily_tips") \
                .select("tip_data") \
                .eq("user_id", user_id) \
                .eq("tip_date", tip_date) \
                .limit(1) \
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["tip_data"]
            return None
        except Exception as e:
            logger.warning(f"Error getting cached tip: {e}")
            return None
    
    async def _cache_tip(self, user_id: str, tip_date: str, tip_data: Dict[str, Any]) -> bool:
        """Cache AI tip in database for today."""
        try:
            self.supabase.table("coach_daily_tips") \
                .upsert({
                    "user_id": user_id,
                    "tip_date": tip_date,
                    "tip_data": tip_data,
                    "is_personalized": tip_data.get("is_personalized", True),
                }) \
                .execute()
            return True
        except Exception as e:
            logger.warning(f"Error caching tip: {e}")
            return False
    
    def _get_curated_tip(self, user_id: str, today: str) -> Dict[str, Any]:
        """Get a curated tip (no AI tokens)."""
        try:
            # Get previously shown tips today
            shown_result = self.supabase.table("coach_behavior_events") \
                .select("event_data") \
                .eq("user_id", user_id) \
                .eq("event_type", "tip_shown") \
                .gte("created_at", today) \
                .execute()
            
            shown_tip_ids = []
            if shown_result.data:
                for event in shown_result.data:
                    tip_id = event.get("event_data", {}).get("tip_id")
                    if tip_id:
                        shown_tip_ids.append(tip_id)
            
            # Filter out already shown tips
            available_tips = [
                (i, t) for i, t in enumerate(self.CURATED_TIPS) 
                if str(i) not in shown_tip_ids
            ]
            
            if not available_tips:
                # All tips shown, reset
                available_tips = list(enumerate(self.CURATED_TIPS))
            
            # Select a random curated tip
            import random
            tip_index, tip = random.choice(available_tips)
            
            return {
                "id": f"curated_{tip_index}",
                "category": tip["category"],
                "title": tip["title"],
                "content": tip["content"],
                "icon": tip["icon"],
                "is_personalized": False,
            }
        except Exception as e:
            logger.warning(f"Error getting curated tip: {e}")
            return {
                "id": "fallback_0",
                "category": self.CURATED_TIPS[0]["category"],
                "title": self.CURATED_TIPS[0]["title"],
                "content": self.CURATED_TIPS[0]["content"],
                "icon": self.CURATED_TIPS[0]["icon"],
                "is_personalized": False,
            }
    
    async def _generate_personalized_tip(
        self, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a personalized tip using Claude AI based on user context.
        
        SPEC-033: Enhanced with seller context for more relevant tips.
        """
        if not self.anthropic_client:
            return None
        
        try:
            # Build seller context section if available
            seller_section = ""
            if context.get("seller_context"):
                seller = context["seller_context"]
                seller_section = f"""
## ABOUT THIS SALES REP:
- Company: {seller.get('company_name', 'Unknown')}
- Industry: {seller.get('industry', 'Unknown')}
- Products/Services: {', '.join(seller.get('products_services', [])[:3]) or 'Not specified'}
- Sales Methodology: {seller.get('sales_methodology', 'Not specified')}
- Target Industries: {', '.join(seller.get('target_industries', [])[:3]) or 'Not specified'}
- Communication Style: {seller.get('communication_style', 'Professional')}
"""
            
            prompt = f"""You are Luna, an AI sales coach. Generate a brief, actionable tip for a sales rep based on their profile and recent activity.
{seller_section}
## RECENT ACTIVITY:
- Research briefs completed: {context.get('research_count', 0)}
- Preparations created: {context.get('prep_count', 0)}
- Follow-ups completed: {context.get('followup_count', 0)}
- Contacts added: {context.get('contact_count', 0)}
- Days since last activity: {context.get('days_inactive', 0)}

## INSTRUCTIONS:
Generate a single, specific tip that would help this sales rep improve.
- If seller context is provided, tailor the tip to their industry, products, or methodology.
- Make it actionable and relevant to their current activity level.
- Keep it brief but impactful.

Format as JSON:
{{
    "category": "research|contacts|preparation|followup|general",
    "title": "Short catchy title (max 5 words)",
    "content": "Practical tip in 1-2 sentences",
    "icon": "relevant emoji"
}}

Only output the JSON, nothing else."""

            message = await self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response
            import json
            response_text = message.content[0].text.strip()
            tip_data = json.loads(response_text)
            tip_data["is_personalized"] = True
            tip_data["id"] = f"ai_{datetime.now().timestamp()}"
            
            return tip_data
            
        except Exception as e:
            logger.warning(f"Failed to generate personalized tip: {e}")
            return None
    
    async def get_predictive_suggestions(
        self, 
        user_id: str,
        organization_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate predictive suggestions based on patterns and timing.
        
        Examples:
        - "You usually create preparations on Tuesdays - want to get started?"
        - "Based on your pattern, this prospect might need a follow-up soon"
        """
        suggestions = []
        
        try:
            # Get user patterns
            patterns_result = self.supabase.table("coach_user_patterns") \
                .select("pattern_type, pattern_data, confidence") \
                .eq("user_id", user_id) \
                .execute()
            
            work_hours_pattern = None
            for pattern in (patterns_result.data or []):
                if pattern["pattern_type"] == "work_hours":
                    work_hours_pattern = pattern["pattern_data"]
                    break
            
            # Suggest based on time of day
            current_hour = datetime.now().hour
            if work_hours_pattern:
                peak_hours = work_hours_pattern.get("peak_hours", [])
                if current_hour in peak_hours:
                    suggestions.append({
                        "type": "timing",
                        "priority": InsightPriority.LOW.value,
                        "title": "Peak productivity time",
                        "message": "This is typically your most productive hour. Great time to tackle important tasks!",
                        "icon": "🚀",
                    })
            
            # Check for overdue follow-ups
            for org_id in organization_ids:
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                
                overdue_preps = self.supabase.table("meeting_preps") \
                    .select("id, prospect_company_name, completed_at") \
                    .eq("organization_id", org_id) \
                    .eq("status", "completed") \
                    .lt("completed_at", week_ago) \
                    .limit(3) \
                    .execute()
                
                for prep in (overdue_preps.data or []):
                    # Check if there's already a follow-up for this prep
                    company = prep.get("prospect_company_name", "")
                    followup_exists = self.supabase.table("followups") \
                        .select("id") \
                        .eq("organization_id", org_id) \
                        .eq("prospect_company_name", company) \
                        .execute()
                    
                    if not followup_exists.data:
                        suggestions.append({
                            "type": "prediction",
                            "priority": InsightPriority.MEDIUM.value,
                            "title": f"Follow-up needed for {company}",
                            "message": f"Your preparation for {company} was completed over a week ago. If the meeting happened, consider creating a follow-up.",
                            "icon": "📞",
                            "action_route": "/dashboard/followup/new",
                        })
            
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(f"Error generating predictive suggestions: {e}")
            return []
    
    async def store_insight(
        self,
        user_id: str,
        organization_id: str,
        insight_type: InsightType,
        insight_data: Dict[str, Any],
        confidence: float = 1.0
    ) -> Optional[str]:
        """
        Store a generated insight for future reference.
        """
        try:
            result = self.supabase.table("coach_success_patterns") \
                .insert({
                    "organization_id": organization_id,
                    "pattern_type": insight_type.value,
                    "pattern_data": insight_data,
                    "sample_size": 1,
                    "confidence": confidence,
                }) \
                .execute()
            
            if result.data:
                return result.data[0]["id"]
            return None
            
        except Exception as e:
            logger.error(f"Error storing insight: {e}")
            return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_user_activity_context(supabase, user_id: str, organization_ids: List[str]) -> Dict[str, Any]:
    """
    Get context about user's recent activity for personalization.
    
    SPEC-033: Enhanced with seller context (company, products, methodology).
    """
    context = {
        "research_count": 0,
        "prep_count": 0,
        "followup_count": 0,
        "contact_count": 0,
        "days_inactive": 0,
        "seller_context": None,  # SPEC-033: Added seller context
    }
    
    try:
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        for org_id in organization_ids:
            # Count recent research
            research = supabase.table("research_briefs") \
                .select("id") \
                .eq("organization_id", org_id) \
                .gte("created_at", week_ago) \
                .execute()
            context["research_count"] += len(research.data or [])
            
            # Count recent preps
            preps = supabase.table("meeting_preps") \
                .select("id") \
                .eq("organization_id", org_id) \
                .gte("created_at", week_ago) \
                .execute()
            context["prep_count"] += len(preps.data or [])
            
            # Count recent followups
            followups = supabase.table("followups") \
                .select("id") \
                .eq("organization_id", org_id) \
                .gte("created_at", week_ago) \
                .execute()
            context["followup_count"] += len(followups.data or [])
        
        # Get last activity
        events = supabase.table("coach_behavior_events") \
            .select("created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if events.data:
            last_activity = datetime.fromisoformat(events.data[0]["created_at"].replace("Z", "+00:00"))
            context["days_inactive"] = (datetime.now(last_activity.tzinfo) - last_activity).days
        
        # SPEC-033: Get seller context (sales profile + company profile)
        context["seller_context"] = await _get_seller_context(supabase, user_id, organization_ids)
        
    except Exception as e:
        logger.error(f"Error getting user activity context: {e}")
    
    return context


async def _get_seller_context(supabase, user_id: str, organization_ids: List[str]) -> Optional[Dict[str, Any]]:
    """
    Get seller context (sales profile + company profile) for personalized tips.
    
    SPEC-033: Luna needs seller context to generate relevant coaching tips.
    """
    seller_context = {}
    
    try:
        # Get sales profile
        sales_result = supabase.table("sales_profiles") \
            .select("full_name, role, sales_methodology, communication_style, target_industries, strengths") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        
        if sales_result.data:
            profile = sales_result.data[0]
            seller_context["full_name"] = profile.get("full_name")
            seller_context["role"] = profile.get("role")
            seller_context["sales_methodology"] = profile.get("sales_methodology")
            seller_context["communication_style"] = profile.get("communication_style")
            seller_context["target_industries"] = profile.get("target_industries") or []
            seller_context["strengths"] = profile.get("strengths") or []
        
        # Get company profile (from first org)
        if organization_ids:
            company_result = supabase.table("company_profiles") \
                .select("company_name, industry, products, core_value_props") \
                .eq("organization_id", organization_ids[0]) \
                .limit(1) \
                .execute()
            
            if company_result.data:
                company = company_result.data[0]
                seller_context["company_name"] = company.get("company_name")
                seller_context["industry"] = company.get("industry")
                # Extract product names from products array
                products = company.get("products", []) or []
                seller_context["products_services"] = [
                    p.get("name") for p in products 
                    if isinstance(p, dict) and p.get("name")
                ]
                seller_context["core_value_props"] = company.get("core_value_props") or []
        
        return seller_context if seller_context else None
        
    except Exception as e:
        logger.warning(f"Error getting seller context for Luna: {e}")
        return None

