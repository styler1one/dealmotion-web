"""
Profile Chat Service - Dynamic AI-powered profile completion through conversation.

This service enables a ChatGPT-like experience for profile onboarding:
1. AI analyzes LinkedIn data and identifies gaps
2. Dynamically generates questions based on what's missing
3. Adapts follow-up questions based on user responses
4. Determines when profile is complete enough
5. Extracts structured data from conversational responses

The conversation feels natural while systematically gathering all needed information.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A single message in the conversation."""
    role: str  # 'assistant' or 'user'
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ChatResponse:
    """Response from the chat service."""
    message: str
    is_complete: bool = False
    completeness_score: float = 0.0
    fields_updated: List[str] = field(default_factory=list)
    current_profile: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)


# =============================================================================
# Profile Field Definitions
# =============================================================================

SALES_PROFILE_FIELDS = {
    # Core identity (usually from LinkedIn)
    "full_name": {"priority": 1, "required": True, "from_linkedin": True},
    "role": {"priority": 1, "required": True, "from_linkedin": True},
    "experience_years": {"priority": 2, "required": False, "from_linkedin": True},
    
    # Sales approach (need to ask)
    "sales_methodology": {"priority": 2, "required": True, "from_linkedin": False,
        "question_hint": "Welke sales methodologie of aanpak gebruik je? (SPIN, Challenger, Consultative, etc.)"},
    "communication_style": {"priority": 2, "required": True, "from_linkedin": False,
        "question_hint": "Hoe zou je je communicatiestijl omschrijven?"},
    
    # Targets (partially from LinkedIn)
    "target_industries": {"priority": 3, "required": True, "from_linkedin": True,
        "question_hint": "In welke industrieën verkoop je het liefst?"},
    "target_company_sizes": {"priority": 3, "required": True, "from_linkedin": False,
        "question_hint": "Welk type bedrijven target je? (Startup, MKB, Enterprise)"},
    "target_regions": {"priority": 3, "required": False, "from_linkedin": True},
    
    # Strengths (from LinkedIn skills)
    "strengths": {"priority": 4, "required": False, "from_linkedin": True},
    
    # Communication preferences (need to ask)
    "email_tone": {"priority": 4, "required": True, "from_linkedin": False,
        "question_hint": "Hoe schrijf je liefst emails? Direct, warm, formeel?"},
    "uses_emoji": {"priority": 5, "required": False, "from_linkedin": False,
        "question_hint": "Gebruik je emoji's in professionele communicatie?"},
    "writing_length_preference": {"priority": 5, "required": False, "from_linkedin": False,
        "question_hint": "Schrijf je liever kort en bondig of uitgebreid?"},
    
    # Goals (always ask)
    "quarterly_goals": {"priority": 3, "required": False, "from_linkedin": False,
        "question_hint": "Wat zijn je huidige sales doelen?"},
}

COMPANY_PROFILE_FIELDS = {
    "company_name": {"priority": 1, "required": True, "from_research": True},
    "industry": {"priority": 1, "required": True, "from_research": True},
    "website": {"priority": 1, "required": True, "from_research": True},
    
    "products": {"priority": 2, "required": True, "from_research": True,
        "question_hint": "Wat zijn jullie belangrijkste producten of diensten?"},
    "core_value_props": {"priority": 2, "required": True, "from_research": True,
        "question_hint": "Wat zijn jullie kernwaarden of value propositions?"},
    "differentiators": {"priority": 2, "required": True, "from_research": False,
        "question_hint": "Wat onderscheidt jullie van concurrenten?"},
    
    "ideal_customer_profile": {"priority": 3, "required": True, "from_research": False,
        "question_hint": "Wie is jullie ideale klant?"},
    "buyer_personas": {"priority": 3, "required": False, "from_research": False,
        "question_hint": "Wie zijn typisch de beslissers bij jullie klanten?"},
    
    "typical_sales_cycle": {"priority": 4, "required": False, "from_research": False,
        "question_hint": "Hoe lang duurt een typisch verkooptraject?"},
    "average_deal_size": {"priority": 4, "required": False, "from_research": False,
        "question_hint": "Wat is jullie gemiddelde dealgrootte?"},
}


class ProfileChatService:
    """
    Dynamic conversational profile completion.
    
    Uses Claude to have a natural conversation that systematically
    gathers profile information while feeling like a helpful chat.
    """
    
    def __init__(self):
        """Initialize the chat service."""
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.completeness_threshold = 0.80  # 80% = good enough
    
    async def start_session(
        self,
        profile_type: str,
        initial_data: Dict[str, Any],
        user_name: Optional[str] = None
    ) -> ChatResponse:
        """
        Start a new chat session with initial greeting.
        
        Args:
            profile_type: 'sales' or 'company'
            initial_data: Data already gathered (LinkedIn/research)
            user_name: User's name for personalization
            
        Returns:
            ChatResponse with opening message
        """
        logger.info(f"[PROFILE_CHAT] Starting {profile_type} session for {user_name}")
        
        # Analyze what we have and what we need
        completeness, filled, missing = self._analyze_completeness(
            profile_type, initial_data
        )
        
        # Generate personalized opening
        opening = await self._generate_opening(
            profile_type=profile_type,
            initial_data=initial_data,
            user_name=user_name,
            filled_fields=filled,
            missing_fields=missing,
            completeness=completeness
        )
        
        return ChatResponse(
            message=opening,
            is_complete=completeness >= self.completeness_threshold,
            completeness_score=completeness,
            current_profile=initial_data,
            suggested_actions=["respond"] if completeness < self.completeness_threshold else ["review_profile"]
        )
    
    async def process_message(
        self,
        profile_type: str,
        current_profile: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> ChatResponse:
        """
        Process a user message and generate the next response.
        
        This is the core of the dynamic conversation:
        1. Extract information from user's response
        2. Update profile with new data
        3. Determine what to ask next (or if complete)
        4. Generate natural follow-up
        
        Args:
            profile_type: 'sales' or 'company'
            current_profile: Current state of profile data
            conversation_history: Previous messages
            user_message: Latest user input
            
        Returns:
            ChatResponse with AI's response and updated profile
        """
        logger.info(f"[PROFILE_CHAT] Processing message: {user_message[:50]}...")
        
        # Step 1: Extract information from user's response
        extracted_data, fields_updated = await self._extract_from_response(
            profile_type=profile_type,
            current_profile=current_profile,
            conversation_history=conversation_history,
            user_message=user_message
        )
        
        # Step 2: Merge into current profile
        updated_profile = {**current_profile, **extracted_data}
        
        # Step 3: Analyze new completeness
        completeness, filled, missing = self._analyze_completeness(
            profile_type, updated_profile
        )
        
        logger.info(f"[PROFILE_CHAT] Completeness: {completeness:.0%}, Missing: {missing}")
        
        # Step 4: Generate next response
        if completeness >= self.completeness_threshold:
            # Profile is complete enough
            response = await self._generate_completion_message(
                profile_type=profile_type,
                profile=updated_profile,
                completeness=completeness
            )
            is_complete = True
            suggested_actions = ["review_profile", "save_profile"]
        else:
            # Ask next question
            response = await self._generate_followup(
                profile_type=profile_type,
                current_profile=updated_profile,
                conversation_history=conversation_history,
                user_message=user_message,
                missing_fields=missing,
                fields_just_updated=fields_updated
            )
            is_complete = False
            suggested_actions = ["respond"]
        
        return ChatResponse(
            message=response,
            is_complete=is_complete,
            completeness_score=completeness,
            fields_updated=fields_updated,
            current_profile=updated_profile,
            suggested_actions=suggested_actions
        )
    
    def _analyze_completeness(
        self,
        profile_type: str,
        profile: Dict[str, Any]
    ) -> Tuple[float, List[str], List[str]]:
        """
        Analyze how complete the profile is.
        
        Returns:
            Tuple of (completeness_score, filled_fields, missing_fields)
        """
        fields = SALES_PROFILE_FIELDS if profile_type == "sales" else COMPANY_PROFILE_FIELDS
        
        filled = []
        missing = []
        total_weight = 0
        filled_weight = 0
        
        for field_name, config in fields.items():
            # Weight by priority (higher priority = more weight)
            weight = 5 - config["priority"] + 1  # Priority 1 = weight 5, Priority 5 = weight 1
            if config["required"]:
                weight *= 2  # Required fields count double
            
            total_weight += weight
            
            value = profile.get(field_name)
            has_value = bool(value) and value != [] and value != {}
            
            if has_value:
                filled.append(field_name)
                filled_weight += weight
            elif config["required"] or config["priority"] <= 3:
                missing.append(field_name)
        
        # Sort missing by priority
        field_priority = {f: fields[f]["priority"] for f in missing if f in fields}
        missing.sort(key=lambda f: field_priority.get(f, 99))
        
        completeness = filled_weight / total_weight if total_weight > 0 else 0
        
        return completeness, filled, missing
    
    async def _generate_opening(
        self,
        profile_type: str,
        initial_data: Dict[str, Any],
        user_name: Optional[str],
        filled_fields: List[str],
        missing_fields: List[str],
        completeness: float
    ) -> str:
        """Generate personalized opening message."""
        
        # Build context about what we know
        known_info = []
        if initial_data.get("full_name"):
            known_info.append(f"naam: {initial_data['full_name']}")
        if initial_data.get("role"):
            known_info.append(f"rol: {initial_data['role']}")
        if initial_data.get("experience_years"):
            known_info.append(f"{initial_data['experience_years']} jaar ervaring")
        if initial_data.get("company_name"):
            known_info.append(f"bedrijf: {initial_data['company_name']}")
        
        prompt = f"""Je bent een vriendelijke AI-assistent die helpt met het aanmaken van een sales profiel.
Je hebt zojuist iemands LinkedIn profiel geanalyseerd en wilt nu een kort gesprek voeren om het profiel compleet te maken.

BEKENDE INFORMATIE:
{json.dumps(initial_data, indent=2, ensure_ascii=False)}

PROFIELCOMPLETENESS: {completeness:.0%}
INGEVULDE VELDEN: {', '.join(filled_fields[:5])}
ONTBREKENDE VELDEN: {', '.join(missing_fields[:5])}

INSTRUCTIES:
1. Begin met een warme, persoonlijke begroeting
2. Bevestig kort wat je al weet (1-2 dingen)
3. Leg uit dat je een paar vragen hebt om het profiel compleet te maken
4. Stel meteen de EERSTE vraag - kies het belangrijkste ontbrekende veld
5. Houd het kort en conversationeel (max 3-4 zinnen)
6. Schrijf in het Nederlands, informeel maar professioneel

BELANGRIJK: Stel slechts ÉÉN vraag per bericht. Wees niet te formeel."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    async def _extract_from_response(
        self,
        profile_type: str,
        current_profile: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Extract structured data from user's conversational response.
        
        Returns:
            Tuple of (extracted_data, fields_updated)
        """
        fields = SALES_PROFILE_FIELDS if profile_type == "sales" else COMPANY_PROFILE_FIELDS
        
        # Build conversation context
        conv_text = ""
        for msg in conversation_history[-6:]:  # Last 6 messages for context
            role = "AI" if msg.get("role") == "assistant" else "User"
            conv_text += f"{role}: {msg.get('content', '')}\n"
        conv_text += f"User: {user_message}\n"
        
        prompt = f"""Analyseer dit gesprek en extraheer gestructureerde profieldata uit het laatste antwoord van de gebruiker.

GESPREK:
{conv_text}

HUIDIGE PROFIELDATA:
{json.dumps(current_profile, indent=2, ensure_ascii=False)}

MOGELIJKE VELDEN OM TE VULLEN:
{json.dumps({k: v.get('question_hint', '') for k, v in fields.items()}, indent=2, ensure_ascii=False)}

INSTRUCTIES:
1. Analyseer wat de gebruiker zojuist heeft gezegd
2. Extraheer ALLEEN informatie die de gebruiker expliciet heeft gegeven
3. Interpreteer synoniemen en informele taal (bijv. "kort en bondig" = "concise")
4. Als de gebruiker iets bevestigt dat al in het profiel staat, hoef je het niet te herhalen

Return ALLEEN valid JSON:
{{
    "extracted_data": {{
        // Alleen velden waar je nieuwe informatie voor hebt
        "field_name": "extracted_value"
    }},
    "fields_updated": ["field1", "field2"]
}}

Als er niets te extraheren is:
{{"extracted_data": {{}}, "fields_updated": []}}"""

        try:
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Clean markdown
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            result = json.loads(content)
            return result.get("extracted_data", {}), result.get("fields_updated", [])
            
        except Exception as e:
            logger.error(f"[PROFILE_CHAT] Extraction failed: {e}")
            return {}, []
    
    async def _generate_followup(
        self,
        profile_type: str,
        current_profile: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        user_message: str,
        missing_fields: List[str],
        fields_just_updated: List[str]
    ) -> str:
        """Generate natural follow-up question."""
        
        fields = SALES_PROFILE_FIELDS if profile_type == "sales" else COMPANY_PROFILE_FIELDS
        
        # Get hints for missing fields
        missing_hints = {
            f: fields[f].get("question_hint", f"Vertel me over {f}")
            for f in missing_fields[:3]
            if f in fields
        }
        
        # Build conversation context
        conv_text = ""
        for msg in conversation_history[-4:]:
            role = "AI" if msg.get("role") == "assistant" else "User"
            conv_text += f"{role}: {msg.get('content', '')}\n"
        conv_text += f"User: {user_message}\n"
        
        prompt = f"""Je bent een vriendelijke AI-assistent die een sales profiel aan het opbouwen bent via een gesprek.

RECENT GESPREK:
{conv_text}

ZOJUIST INGEVULD: {', '.join(fields_just_updated) if fields_just_updated else 'Niets nieuws'}

NOG ONTBREKEND (in volgorde van prioriteit):
{json.dumps(missing_hints, indent=2, ensure_ascii=False)}

INSTRUCTIES:
1. Reageer kort en natuurlijk op wat de gebruiker net zei (erken hun antwoord)
2. Stel vervolgens ÉÉN vraag over het belangrijkste ontbrekende veld
3. Houd het conversationeel en niet als een formulier
4. Varieer in hoe je vragen stelt
5. Max 2-3 zinnen totaal
6. Schrijf in het Nederlands

Als de gebruiker iets interessants zei, kun je kort doorvragen voordat je naar het volgende onderwerp gaat."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    async def _generate_completion_message(
        self,
        profile_type: str,
        profile: Dict[str, Any],
        completeness: float
    ) -> str:
        """Generate message when profile is complete enough."""
        
        prompt = f"""Je bent een vriendelijke AI-assistent die zojuist een sales profiel heeft afgerond via een gesprek.

PROFIELCOMPLETENESS: {completeness:.0%}

PROFIEL SAMENVATTING:
- Naam: {profile.get('full_name', 'Onbekend')}
- Rol: {profile.get('role', 'Onbekend')}
- Methodologie: {profile.get('sales_methodology', 'Niet gespecificeerd')}
- Communicatiestijl: {profile.get('communication_style', 'Niet gespecificeerd')}

INSTRUCTIES:
1. Bedank de gebruiker voor het gesprek
2. Geef een korte samenvatting van wat je hebt geleerd (1-2 zinnen)
3. Zeg dat hun profiel nu klaar is om te gebruiken
4. Nodig uit om het profiel te bekijken
5. Kort en enthousiast (max 3-4 zinnen)
6. Nederlands, informeel maar professioneel"""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()


# Singleton instance
_profile_chat_service: Optional[ProfileChatService] = None


def get_profile_chat_service() -> ProfileChatService:
    """Get or create the ProfileChatService singleton."""
    global _profile_chat_service
    if _profile_chat_service is None:
        _profile_chat_service = ProfileChatService()
    return _profile_chat_service

