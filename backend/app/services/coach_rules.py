"""
AI Sales Coach "Luna" - Rule Engine
TASK-029 / SPEC-028

This service evaluates rules to generate suggestions based on user context.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.models.coach import (
    RuleDefinition,
    SuggestionType,
    SuggestionBase,
    UserContext,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RULE DEFINITIONS
# =============================================================================

RULES: List[RuleDefinition] = [
    # Rule 1: Research without contacts
    RuleDefinition(
        id="research-needs-contacts",
        name="Research needs contacts",
        description="Research is complete but no contacts have been added",
        suggestion_type=SuggestionType.ADD_CONTACTS,
        base_priority=80,
        icon="👤",
        title_template="Add contacts to {company}",
        description_template="Your research for {company} is ready. Add contacts to personalize your preparation.",
        reason_template="Research completed, no contacts yet",
        action_route_template="/dashboard/research/{research_id}",
        action_label="Add Contacts",
    ),
    
    # Rule 2: Research with contacts, no prep
    RuleDefinition(
        id="ready-for-prep",
        name="Ready for preparation",
        description="Research and contacts are ready, but no preparation exists",
        suggestion_type=SuggestionType.CREATE_PREP,
        base_priority=75,
        icon="📋",
        title_template="Create preparation for {company}",
        description_template="Research and contacts are ready for {company}. Create your meeting preparation.",
        reason_template="{contact_count} contacts analyzed",
        action_route_template="/dashboard/preparation",
        action_label="Create Prep",
    ),
    
    # Rule 3: Prep completed, no follow-up
    RuleDefinition(
        id="needs-followup",
        name="Needs follow-up",
        description="Preparation is complete but no follow-up has been created",
        suggestion_type=SuggestionType.CREATE_FOLLOWUP,
        base_priority=70,
        icon="🎙️",
        title_template="Create follow-up for {company}",
        description_template="Your meeting prep for {company} is ready. After your meeting, upload the recording.",
        reason_template="Preparation completed on {prep_date}",
        action_route_template="/dashboard/followup",
        action_label="Create Follow-up",
    ),
    
    # Rule 4: Follow-up without generated actions
    RuleDefinition(
        id="generate-actions",
        name="Generate follow-up actions",
        description="Follow-up is complete but no actions have been generated",
        suggestion_type=SuggestionType.GENERATE_ACTION,
        base_priority=65,
        icon="✨",
        title_template="Generate actions for {company}",
        description_template="Your follow-up for {company} is ready. Generate a customer report or other actions.",
        reason_template="Follow-up completed, no actions yet",
        action_route_template="/dashboard/followup/{followup_id}",
        action_label="Generate Actions",
    ),
    
    # Rule 5: Overdue prospect (no activity in 7+ days)
    RuleDefinition(
        id="overdue-prospect",
        name="Overdue prospect",
        description="No activity on this prospect for 7+ days",
        suggestion_type=SuggestionType.OVERDUE_PROSPECT,
        base_priority=60,
        icon="⏰",
        title_template="{company} needs attention",
        description_template="No activity for {days} days. Consider following up.",
        reason_template="Last activity: {last_activity}",
        action_route_template="/dashboard/research/{research_id}",
        action_label="View Prospect",
    ),
    
    # Rule 6: Complete sales profile
    RuleDefinition(
        id="complete-sales-profile",
        name="Complete sales profile",
        description="Sales profile is not complete",
        suggestion_type=SuggestionType.COMPLETE_PROFILE,
        base_priority=90,
        icon="👤",
        title_template="Complete your sales profile",
        description_template="A complete profile helps generate better, personalized content.",
        reason_template="Profile incomplete",
        action_route_template="/onboarding",
        action_label="Complete Profile",
    ),
    
    # Rule 7: Complete company profile
    RuleDefinition(
        id="complete-company-profile",
        name="Complete company profile",
        description="Company profile is not complete",
        suggestion_type=SuggestionType.COMPLETE_PROFILE,
        base_priority=85,
        icon="🏢",
        title_template="Add your company profile",
        description_template="Adding your company helps personalize research and preparations.",
        reason_template="Company not set up",
        action_route_template="/onboarding/company",
        action_label="Add Company",
    ),
]


# =============================================================================
# RULE ENGINE
# =============================================================================

class CoachRuleEngine:
    """Evaluates rules against user context to generate suggestions."""
    
    def __init__(self):
        self.rules = {rule.id: rule for rule in RULES}
    
    def evaluate_all(self, context: UserContext) -> List[SuggestionBase]:
        """Evaluate all rules and return matching suggestions."""
        suggestions = []
        
        # Rules that overlap with Autopilot proposals - skip if autopilot enabled
        # Autopilot handles: prep suggestions, follow-up suggestions, overdue prospects
        skip_overlapping_rules = context.autopilot_enabled
        
        # Profile completeness rules (never skip - Autopilot doesn't handle these)
        if not context.has_sales_profile:
            suggestions.append(self._create_suggestion(
                self.rules["complete-sales-profile"],
                {}
            ))
        
        if not context.has_company_profile:
            suggestions.append(self._create_suggestion(
                self.rules["complete-company-profile"],
                {}
            ))
        
        # Research without contacts
        for research in context.research_without_contacts:
            suggestions.append(self._create_suggestion(
                self.rules["research-needs-contacts"],
                {
                    "company": research.get("company_name", "Unknown"),
                    "research_id": research.get("id", ""),
                }
            ))
        
        # Preps without follow-up
        # SKIP if Autopilot enabled - Autopilot handles this with followup_pack proposals
        if not skip_overlapping_rules:
            for prep in context.preps_without_followup:
                suggestions.append(self._create_suggestion(
                    self.rules["needs-followup"],
                    {
                        "company": prep.get("prospect_company_name", "Unknown"),
                        "prep_date": self._format_date(prep.get("completed_at")),
                    }
                ))
        
        # Follow-ups without actions
        for followup in context.followups_without_actions:
            suggestions.append(self._create_suggestion(
                self.rules["generate-actions"],
                {
                    "company": followup.get("prospect_company_name", "Unknown"),
                    "followup_id": followup.get("id", ""),
                }
            ))
        
        # Inactive prospects
        # SKIP if Autopilot enabled - Autopilot handles this with reactivation proposals
        if not skip_overlapping_rules:
            for prospect in context.inactive_prospects:
                days = prospect.get("days_inactive", 7)
                suggestions.append(self._create_suggestion(
                    self.rules["overdue-prospect"],
                    {
                        "company": prospect.get("company_name", "Unknown"),
                        "days": days,
                        "last_activity": prospect.get("last_activity", "Unknown"),
                        "research_id": prospect.get("research_id", ""),
                    },
                    priority_boost=min(days - 7, 20)  # Boost priority based on how overdue
                ))
        
        # Sort by priority (highest first)
        suggestions.sort(key=lambda s: s.priority, reverse=True)
        
        return suggestions
    
    def _create_suggestion(
        self, 
        rule: RuleDefinition, 
        variables: Dict[str, Any],
        priority_boost: float = 0
    ) -> SuggestionBase:
        """Create a suggestion from a rule definition with variable substitution."""
        
        def substitute(template: Optional[str]) -> Optional[str]:
            if not template:
                return None
            try:
                return template.format(**variables)
            except KeyError as e:
                logger.warning(f"Missing variable in template: {e}")
                return template
        
        return SuggestionBase(
            suggestion_type=rule.suggestion_type,
            title=substitute(rule.title_template) or rule.name,
            description=substitute(rule.description_template) or rule.description,
            reason=substitute(rule.reason_template),
            priority=min(100, rule.base_priority + priority_boost),
            action_route=substitute(rule.action_route_template),
            action_label=rule.action_label,
            icon=rule.icon,
            related_entity_type=None,  # Will be set by caller if needed
            related_entity_id=variables.get("research_id") or variables.get("followup_id"),
        )
    
    def _format_date(self, date_str: Optional[str]) -> str:
        """Format a date string for display."""
        if not date_str:
            return "Unknown"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%b %d")
        except (ValueError, AttributeError):
            return str(date_str)[:10]
    
    def adjust_priority_with_patterns(
        self, 
        suggestion: SuggestionBase, 
        patterns: Dict[str, Any]
    ) -> SuggestionBase:
        """Adjust suggestion priority based on learned patterns."""
        
        priority = suggestion.priority
        suggestion_type = suggestion.suggestion_type.value
        
        # Check dismiss patterns - reduce priority if user often dismisses this type
        dismiss_patterns = patterns.get("dismiss_patterns", {})
        dismiss_rate = dismiss_patterns.get(suggestion_type, 0)
        if dismiss_rate > 0.5:  # User dismisses more than 50% of this type
            priority -= 20
        elif dismiss_rate > 0.3:
            priority -= 10
        
        # Check preferred actions - boost if user often clicks this type
        click_patterns = patterns.get("click_patterns", {})
        click_rate = click_patterns.get(suggestion_type, 0)
        if click_rate > 0.5:
            priority += 15
        elif click_rate > 0.3:
            priority += 8
        
        # Ensure priority stays in bounds
        priority = max(0, min(100, priority))
        
        # Create new suggestion with adjusted priority
        return SuggestionBase(
            **{**suggestion.model_dump(), "priority": priority}
        )


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

async def build_user_context(
    supabase,
    user_id: str,
    organization_ids: list[str]
) -> UserContext:
    """
    Build the user context by gathering all relevant data.
    This is used by the rule engine to evaluate suggestions.
    
    Note: organization_ids is a list to support users who may be members
    of multiple organizations. All data should be stored under the user's
    primary organization from organization_members table.
    """
    
    # Use first org as primary for backward compatibility
    primary_org_id = organization_ids[0] if organization_ids else ""
    
    context = UserContext(
        user_id=user_id,
        organization_id=primary_org_id,
        current_hour=datetime.now().hour,
        current_day_of_week=datetime.now().weekday(),
    )
    
    try:
        # Check if Autopilot is enabled for this user (to avoid duplicate suggestions)
        autopilot_settings = supabase.table("autopilot_settings") \
            .select("enabled") \
            .eq("user_id", user_id) \
            .execute()
        context.autopilot_enabled = bool(
            autopilot_settings.data and 
            autopilot_settings.data[0].get("enabled", False)
        )
    except Exception as e:
        logger.warning(f"Failed to check autopilot settings: {e}")
        context.autopilot_enabled = False
    
    try:
        # Check sales profile (user-based, not org-based)
        profile_result = supabase.table("sales_profiles") \
            .select("full_name") \
            .eq("user_id", user_id) \
            .execute()
        context.has_sales_profile = bool(
            profile_result.data and 
            profile_result.data[0].get("full_name")
        )
        
        # Check company profile - check ALL organizations
        context.has_company_profile = False
        for org_id in organization_ids:
            company_result = supabase.table("company_profiles") \
                .select("company_name") \
                .eq("organization_id", org_id) \
                .execute()
            if company_result.data and company_result.data[0].get("company_name"):
                context.has_company_profile = True
                break
        
        # Get completed research briefs - check ALL organizations
        all_research = []
        for org_id in organization_ids:
            research_result = supabase.table("research_briefs") \
                .select("id, company_name, prospect_id, status, completed_at") \
                .eq("organization_id", org_id) \
                .eq("status", "completed") \
                .execute()
            if research_result.data:
                all_research.extend(research_result.data)
        
        if all_research:
            context.research_briefs = all_research
            
            # For each research, check if it has contacts
            for research in all_research:
                prospect_id = research.get("prospect_id")
                if prospect_id:
                    contacts_result = supabase.table("prospect_contacts") \
                        .select("id") \
                        .eq("prospect_id", prospect_id) \
                        .execute()
                    
                    if not contacts_result.data:
                        context.research_without_contacts.append(research)
        
        # Get completed preps - check ALL organizations
        all_preps = []
        all_followups = []
        for org_id in organization_ids:
            preps_result = supabase.table("meeting_preps") \
                .select("id, prospect_company_name, status, completed_at") \
                .eq("organization_id", org_id) \
                .eq("status", "completed") \
                .execute()
            if preps_result.data:
                all_preps.extend(preps_result.data)
            
            followups_result = supabase.table("followups") \
                .select("prospect_company_name") \
                .eq("organization_id", org_id) \
                .execute()
            if followups_result.data:
                all_followups.extend(followups_result.data)
        
        if all_preps:
            context.preps_completed = all_preps
            
            followup_companies = {
                f.get("prospect_company_name", "").lower() 
                for f in all_followups
            }
            
            for prep in all_preps:
                company = prep.get("prospect_company_name", "").lower()
                if company not in followup_companies:
                    context.preps_without_followup.append(prep)
        
        # Get completed follow-ups - check ALL organizations
        all_completed_followups = []
        for org_id in organization_ids:
            followups_result = supabase.table("followups") \
                .select("id, prospect_company_name, status, completed_at") \
                .eq("organization_id", org_id) \
                .eq("status", "completed") \
                .execute()
            if followups_result.data:
                all_completed_followups.extend(followups_result.data)
        
        if all_completed_followups:
            context.followups_completed = all_completed_followups
            
            # Check which follow-ups have generated actions
            for followup in all_completed_followups:
                actions_result = supabase.table("followup_actions") \
                    .select("id") \
                    .eq("followup_id", followup.get("id")) \
                    .execute()
                
                if not actions_result.data:
                    context.followups_without_actions.append(followup)
        
        # Get inactive prospects (no activity in 7+ days) - check ALL organizations
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        for org_id in organization_ids:
            inactive_research = supabase.table("research_briefs") \
                .select("id, company_name, completed_at") \
                .eq("organization_id", org_id) \
                .eq("status", "completed") \
                .lt("completed_at", week_ago) \
                .execute()
            
            if inactive_research.data:
                for research in inactive_research.data:
                    days_ago = (datetime.now() - datetime.fromisoformat(
                        research.get("completed_at", datetime.now().isoformat()).replace("Z", "+00:00")
                    )).days
                    
                    if days_ago >= 7:
                        context.inactive_prospects.append({
                            "company_name": research.get("company_name"),
                            "research_id": research.get("id"),
                            "days_inactive": days_ago,
                            "last_activity": research.get("completed_at"),
                        })
        
        # Get learned patterns
        patterns_result = supabase.table("coach_user_patterns") \
            .select("pattern_type, pattern_data") \
            .eq("user_id", user_id) \
            .execute()
        
        if patterns_result.data:
            for pattern in patterns_result.data:
                context.patterns[pattern.get("pattern_type")] = pattern.get("pattern_data", {})
        
    except Exception as e:
        logger.error(f"Error building user context: {e}")
    
    return context


# Singleton instance
rule_engine = CoachRuleEngine()

