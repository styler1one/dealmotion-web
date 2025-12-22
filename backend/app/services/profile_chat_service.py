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
    "email_signoff": {"priority": 5, "required": False, "from_linkedin": False,
        "question_hint": "Hoe sluit je emails af? (bijv. 'Groet', 'Met vriendelijke groet', etc.)"},
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
        
        Also considers linkedin_raw data as filled fields.
        
        Returns:
            Tuple of (completeness_score, filled_fields, missing_fields)
        """
        fields = SALES_PROFILE_FIELDS if profile_type == "sales" else COMPANY_PROFILE_FIELDS
        
        # Check linkedin_raw for additional data
        linkedin_raw = profile.get("linkedin_raw", {})
        
        filled = []
        missing = []
        total_weight = 0
        filled_weight = 0
        
        # Map linkedin_raw fields to profile fields
        linkedin_field_map = {
            "full_name": ["headline"],  # Can extract from headline
            "role": ["headline"],
            "experience_years": ["experience_years"],
            "strengths": ["skills"],
            "target_industries": [],  # Need to ask
            "target_regions": ["location"],
        }
        
        for field_name, config in fields.items():
            # Weight by priority (higher priority = more weight)
            weight = 5 - config["priority"] + 1  # Priority 1 = weight 5, Priority 5 = weight 1
            if config["required"]:
                weight *= 2  # Required fields count double
            
            total_weight += weight
            
            # Check profile data
            value = profile.get(field_name)
            has_value = bool(value) and value != [] and value != {}
            
            # Also check linkedin_raw for mapped fields
            if not has_value and field_name in linkedin_field_map:
                for linkedin_field in linkedin_field_map[field_name]:
                    linkedin_value = linkedin_raw.get(linkedin_field)
                    if linkedin_value:
                        has_value = True
                        break
            
            # Special cases: if we have about_section or experience_section, count related fields
            if not has_value:
                if field_name == "full_name" and linkedin_raw.get("about_section"):
                    has_value = True  # We can likely extract from about
                elif field_name == "strengths" and linkedin_raw.get("skills"):
                    has_value = True
                elif field_name == "experience_years" and linkedin_raw.get("experience_section"):
                    has_value = True  # Can be derived from experience
            
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
        
        # Extract LinkedIn raw data if available (from magic onboarding)
        linkedin_raw = initial_data.get("linkedin_raw", {})
        
        # Build comprehensive context about what we know
        known_info = []
        
        # Basic info
        name = initial_data.get("full_name") or linkedin_raw.get("headline", "").split(" - ")[0] if linkedin_raw.get("headline") else None
        if name:
            known_info.append(f"Naam: {name}")
        
        role = initial_data.get("role") or linkedin_raw.get("headline")
        if role:
            known_info.append(f"Rol/Headline: {role}")
        
        if initial_data.get("experience_years") or linkedin_raw.get("experience_years"):
            years = initial_data.get("experience_years") or linkedin_raw.get("experience_years")
            known_info.append(f"Ervaring: {years} jaar")
        
        # Rich LinkedIn data
        about = linkedin_raw.get("about_section")
        if about:
            known_info.append(f"LinkedIn About: {about[:500]}...")
        
        experience = linkedin_raw.get("experience_section")
        if experience:
            known_info.append(f"Werkervaring: {experience[:400]}...")
        
        skills = linkedin_raw.get("skills") or initial_data.get("strengths", [])
        if skills:
            known_info.append(f"Skills: {', '.join(skills[:10])}")
        
        ai_summary = linkedin_raw.get("ai_summary")
        if ai_summary:
            known_info.append(f"Profiel samenvatting: {ai_summary[:300]}...")
        
        known_info_text = "\n".join(known_info) if known_info else "Geen informatie beschikbaar"
        
        prompt = f"""Je bent een vriendelijke AI-assistent die helpt met het aanmaken van een sales profiel.
Je hebt zojuist iemands LinkedIn profiel geanalyseerd en wilt nu een kort gesprek voeren om het profiel compleet te maken.

=== LINKEDIN DATA DIE JE HEBT ===
{known_info_text}

=== HUIDIGE PROFIELDATA ===
{json.dumps({k: v for k, v in initial_data.items() if k != 'linkedin_raw'}, indent=2, ensure_ascii=False)}

PROFIELCOMPLETENESS: {completeness:.0%}
INGEVULDE VELDEN: {', '.join(filled_fields[:5])}
ONTBREKENDE VELDEN: {', '.join(missing_fields[:5])}

INSTRUCTIES:
1. Begin met een warme, persoonlijke begroeting - noem hun naam als je die hebt
2. Laat zien dat je hun LinkedIn profiel hebt gelezen - noem iets specifieks (bijv. hun ervaring, huidige rol, of iets uit hun about sectie)
3. Leg uit dat je een paar aanvullende vragen hebt om het profiel compleet te maken
4. Stel meteen de EERSTE vraag - kies het belangrijkste ontbrekende veld
5. Houd het kort en conversationeel (max 4-5 zinnen)
6. Schrijf in het Nederlands, informeel maar professioneel

BELANGRIJK: 
- Stel slechts ÉÉN vraag per bericht
- Toon dat je de LinkedIn data daadwerkelijk hebt gelezen
- Als je veel info hebt, benoem dan dat je al veel weet"""

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
        
        # Build profile summary for context
        profile_summary_items = []
        if current_profile.get("full_name"):
            profile_summary_items.append(f"Naam: {current_profile['full_name']}")
        if current_profile.get("role"):
            profile_summary_items.append(f"Rol: {current_profile['role']}")
        if current_profile.get("experience_years"):
            profile_summary_items.append(f"Ervaring: {current_profile['experience_years']} jaar")
        if current_profile.get("sales_methodology"):
            profile_summary_items.append(f"Methodologie: {current_profile['sales_methodology']}")
        if current_profile.get("communication_style"):
            profile_summary_items.append(f"Stijl: {current_profile['communication_style']}")
        if current_profile.get("strengths"):
            profile_summary_items.append(f"Sterktes: {', '.join(current_profile['strengths'][:3])}")
        if current_profile.get("target_industries"):
            profile_summary_items.append(f"Industries: {', '.join(current_profile['target_industries'][:3])}")
        if current_profile.get("quarterly_goals"):
            profile_summary_items.append(f"Doelen: {current_profile['quarterly_goals'][:100]}")
        
        profile_summary = "\n".join(profile_summary_items) if profile_summary_items else "Nog geen data"
        
        prompt = f"""Je bent een vriendelijke AI-assistent die een sales profiel aan het opbouwen bent via een gesprek.

RECENT GESPREK:
{conv_text}

ZOJUIST INGEVULD: {', '.join(fields_just_updated) if fields_just_updated else 'Niets nieuws'}

=== WAT IK NU WEET (ACTUEEL PROFIEL) ===
{profile_summary}

NOG ONTBREKEND (in volgorde van prioriteit):
{json.dumps(missing_hints, indent=2, ensure_ascii=False)}

INSTRUCTIES:
1. Als de gebruiker vraagt wat je weet/opslaat/gebruikt: geef een CONCRETE opsomming van de data uit "WAT IK NU WEET"
2. Anders: reageer kort en natuurlijk op wat de gebruiker zei
3. Als er nog dingen ontbreken, stel ÉÉN vraag over het belangrijkste ontbrekende veld
4. Houd het conversationeel, NIET als een formulier
5. HERHAAL NIET wat je al eerder hebt gezegd
6. Max 3-4 zinnen totaal
7. Schrijf in het Nederlands

BELANGRIJK: Als de gebruiker vraagt over de data/instructies/systeem, wees transparant over wat je voor hen opslaat."""

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
        
        # Build detailed summary of what we know
        strengths = profile.get('strengths', [])
        targets = profile.get('target_industries', [])
        goals = profile.get('quarterly_goals', '')
        
        prompt = f"""Je bent een vriendelijke AI-assistent die zojuist een sales profiel heeft afgerond via een gesprek.

PROFIELCOMPLETENESS: {completeness:.0%}

=== VOLLEDIG OPGEBOUWD PROFIEL ===
- Naam: {profile.get('full_name', 'Onbekend')}
- Rol: {profile.get('role', 'Onbekend')}
- Ervaring: {profile.get('experience_years', '?')} jaar
- Sales methodologie: {profile.get('sales_methodology', 'Niet gespecificeerd')}
- Communicatiestijl: {profile.get('communication_style', 'Niet gespecificeerd')}
- Sterktes: {', '.join(strengths[:5]) if strengths else 'Niet gespecificeerd'}
- Target industrieën: {', '.join(targets[:3]) if targets else 'Niet gespecificeerd'}
- Email toon: {profile.get('email_tone', 'Niet gespecificeerd')}
- Kwartaaldoelen: {goals[:100] if goals else 'Niet gespecificeerd'}

INSTRUCTIES:
1. Geef een CONCRETE samenvatting van wat je hebt opgeslagen (noem specifieke dingen uit het profiel)
2. Leg uit dat deze informatie wordt gebruikt om:
   - Meeting preps te personaliseren
   - Emails in hun stijl te schrijven
   - Gesprekstips af te stemmen op hun aanpak
3. Nodig uit om op "Profiel Opslaan" te klikken
4. Kort maar informatief (max 5 zinnen)
5. Nederlands, vriendelijk en professioneel
6. HERHAAL NIET wat je al eerder hebt gezegd

Geef een duidelijke samenvatting van wat je hebt geleerd, niet een generieke afsluiting."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    async def generate_sales_narrative(
        self,
        profile: Dict[str, Any],
        linkedin_raw: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> str:
        """
        Generate a personal sales narrative/story based on the profile data.
        This creates a compelling, personalized story about the sales professional.
        
        Args:
            profile: Profile data dict
            linkedin_raw: Optional LinkedIn enrichment data
            language: Output language code (en, nl, de, etc.)
        """
        
        linkedin_data = linkedin_raw or {}
        about_section = linkedin_data.get("about_section", "")
        experience_section = linkedin_data.get("experience_section", "")
        skills = linkedin_data.get("skills", [])
        headline = linkedin_data.get("headline", "")
        
        # Language-specific instructions
        lang_instructions = {
            "nl": "Schrijf in het Nederlands",
            "en": "Write in English",
            "de": "Schreibe auf Deutsch",
            "fr": "Écrivez en français",
            "es": "Escribe en español",
        }
        lang_instruction = lang_instructions.get(language, "Write in English")
        
        prompt = f"""You are a professional copywriter creating personal stories for sales professionals.

Write an engaging, personal narrative (3-4 paragraphs) about this sales professional. The story should:
- Be written in third person
- Sound authentic and relatable
- Highlight key points from their experience and approach
- End with what drives them and how they create value

=== PROFILE DATA ===
Name: {profile.get('full_name', 'Unknown')}
Role: {profile.get('role', 'Sales Professional')}
Experience: {profile.get('experience_years', '?')} years
Methodology: {profile.get('sales_methodology', 'Not specified')}
Communication Style: {profile.get('communication_style', 'Not specified')}
Strengths: {', '.join(profile.get('strengths', [])) if profile.get('strengths') else 'Not specified'}
Target Industries: {', '.join(profile.get('target_industries', [])) if profile.get('target_industries') else 'Not specified'}
Target Company Sizes: {', '.join(profile.get('target_company_sizes', [])) if profile.get('target_company_sizes') else 'Not specified'}
Quarterly Goals: {profile.get('quarterly_goals', 'Not specified')}
Email Tone: {profile.get('email_tone', 'Not specified')}

=== LINKEDIN INFORMATION ===
Headline: {headline}
About: {about_section[:1000] if about_section else 'Not available'}
Experience: {experience_section[:1000] if experience_section else 'Not available'}
Skills: {', '.join(skills[:10]) if skills else 'Not available'}

=== INSTRUCTIONS ===
1. Write a PERSONAL story, not a bullet list
2. Use concrete details from the data
3. {lang_instruction}
4. 3-4 paragraphs, separated by double newlines
5. Do NOT start with the name - begin with a powerful opening about their expertise or approach
6. Make it recognizable for the person themselves
7. End with their drive/motivation or how they create impact

Write the narrative:"""

        try:
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"[PROFILE_CHAT] Failed to generate sales narrative: {e}")
            return ""
    
    async def generate_ai_summary(
        self,
        profile: Dict[str, Any],
        language: str = "en"
    ) -> str:
        """
        Generate a short AI summary of the profile.
        
        Args:
            profile: Profile data dict
            language: Output language code (en, nl, de, etc.)
        """
        
        # Language-specific instructions
        lang_instructions = {
            "nl": "Schrijf een professionele, beknopte samenvatting in het Nederlands",
            "en": "Write a professional, concise summary in English",
            "de": "Schreibe eine professionelle, prägnante Zusammenfassung auf Deutsch",
            "fr": "Rédigez un résumé professionnel et concis en français",
            "es": "Escribe un resumen profesional y conciso en español",
        }
        lang_instruction = lang_instructions.get(language, "Write a professional, concise summary in English")
        
        prompt = f"""Write a short summary (2-3 sentences) of this sales professional:

Name: {profile.get('full_name', 'Unknown')}
Role: {profile.get('role', 'Sales Professional')}
Experience: {profile.get('experience_years', '?')} years
Strengths: {', '.join(profile.get('strengths', [])) if profile.get('strengths') else 'Not specified'}
Target Industries: {', '.join(profile.get('target_industries', [])) if profile.get('target_industries') else 'Not specified'}

{lang_instruction}:"""

        try:
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"[PROFILE_CHAT] Failed to generate AI summary: {e}")
            return ""


# Singleton instance
_profile_chat_service: Optional[ProfileChatService] = None


def get_profile_chat_service() -> ProfileChatService:
    """Get or create the ProfileChatService singleton."""
    global _profile_chat_service
    if _profile_chat_service is None:
        _profile_chat_service = ProfileChatService()
    return _profile_chat_service

