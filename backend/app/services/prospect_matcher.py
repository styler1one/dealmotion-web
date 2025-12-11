"""
Prospect Matcher Service - Match calendar meetings to prospects
SPEC-038: Meetings & Calendar Integration
"""
from typing import Optional, List, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import re
import logging

from supabase import Client

logger = logging.getLogger(__name__)


@dataclass
class ProspectMatch:
    """A potential match between a meeting and a prospect."""
    prospect_id: str
    company_name: str
    confidence: float  # 0.0 - 1.0
    match_reason: str


@dataclass
class MatchResult:
    """Result of matching a meeting to prospects."""
    meeting_id: str
    best_match: Optional[ProspectMatch] = None
    all_matches: List[ProspectMatch] = None
    auto_linked: bool = False
    matched_contact_ids: List[str] = None  # Contact IDs that matched
    
    def __post_init__(self):
        if self.all_matches is None:
            self.all_matches = []
        if self.matched_contact_ids is None:
            self.matched_contact_ids = []


class ProspectMatcher:
    """Service for matching calendar meetings to prospects."""
    
    # Minimum confidence for auto-linking
    AUTO_LINK_THRESHOLD = 0.8
    
    # Weights for different matching signals
    WEIGHT_TITLE_EXACT = 0.9
    WEIGHT_TITLE_PARTIAL = 0.6
    WEIGHT_EMAIL_DOMAIN = 0.85  # Increased: website domain match is reliable
    WEIGHT_CONTACT_EMAIL_EXACT = 0.95  # Direct match with known contact
    WEIGHT_CONTACT_DOMAIN = 0.85  # Same domain as known contact
    WEIGHT_CONTACT_NAME_MATCH = 0.92  # Full name matches a contact (high confidence!)
    WEIGHT_CONTACT_NAME_PARTIAL = 0.82  # First or last name matches
    WEIGHT_ATTENDEE_NAME = 0.4
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    def normalize_company_name(self, name: str) -> str:
        """Normalize company name for matching."""
        if not name:
            return ""
        # Lowercase, remove common suffixes
        normalized = name.lower().strip()
        # Remove common company suffixes
        suffixes = [
            ' inc', ' inc.', ' llc', ' ltd', ' ltd.', ' limited',
            ' corp', ' corp.', ' corporation', ' bv', ' b.v.',
            ' nv', ' n.v.', ' gmbh', ' ag', ' sa', ' srl',
            ' co', ' co.', ' company', ' group', ' holding',
        ]
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        return normalized
    
    def extract_domain_from_website(self, website: str) -> Optional[str]:
        """Extract domain from website URL."""
        if not website:
            return None
        try:
            # Add scheme if missing
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            parsed = urlparse(website)
            domain = parsed.netloc or parsed.path
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain.lower()
        except Exception:
            return None
    
    def extract_domain_from_email(self, email: str) -> Optional[str]:
        """Extract domain from email address."""
        if not email or '@' not in email:
            return None
        return email.split('@')[1].lower()
    
    def calculate_title_match(self, meeting_title: str, company_name: str) -> float:
        """Calculate confidence based on meeting title matching company name."""
        if not meeting_title or not company_name:
            return 0.0
        
        title_normalized = self.normalize_company_name(meeting_title)
        company_normalized = self.normalize_company_name(company_name)
        
        # Exact match (full company name in title)
        if company_normalized in title_normalized:
            return self.WEIGHT_TITLE_EXACT
        
        # Check if significant words from company name are in title
        company_words = set(company_normalized.split())
        title_words = set(title_normalized.split())
        
        if not company_words:
            return 0.0
        
        # Calculate overlap
        overlap = company_words.intersection(title_words)
        overlap_ratio = len(overlap) / len(company_words)
        
        # At least one significant word matches
        if overlap_ratio >= 0.5:
            return self.WEIGHT_TITLE_PARTIAL * overlap_ratio
        
        return 0.0
    
    def calculate_email_domain_match(
        self, 
        attendee_emails: List[str], 
        prospect_website: str,
        prospect_contact_email: str
    ) -> float:
        """Calculate confidence based on email domain matching."""
        if not attendee_emails:
            return 0.0
        
        # Get domains to match against
        match_domains = set()
        
        # From website
        website_domain = self.extract_domain_from_website(prospect_website)
        if website_domain:
            match_domains.add(website_domain)
        
        # From contact email
        contact_domain = self.extract_domain_from_email(prospect_contact_email)
        if contact_domain:
            match_domains.add(contact_domain)
        
        if not match_domains:
            return 0.0
        
        # Check attendee emails
        for email in attendee_emails:
            email_domain = self.extract_domain_from_email(email)
            if email_domain and email_domain in match_domains:
                return self.WEIGHT_EMAIL_DOMAIN
        
        return 0.0
    
    async def get_contacts_for_matching(self, organization_id: str) -> dict:
        """
        Fetch all contacts for the organization and build lookup structures.
        
        Returns:
            {
                "by_email": {email: {"prospect_id": str, "contact_id": str}},
                "by_domain": {domain: [{"prospect_id": str, "contact_id": str}]},
                "by_name": {normalized_name: [{"prospect_id": str, "contact_id": str, "full_name": str}]},
                "prospect_names": {prospect_id: company_name}
            }
        """
        try:
            # Fetch contacts with their prospect info (include name field!)
            # Note: table is "prospect_contacts" not "contacts"
            # Note: contacts have a single "name" field, not first_name/last_name
            contacts_result = self.supabase.table("prospect_contacts").select(
                "id, email, name, prospect_id, prospects(id, company_name)"
            ).eq("organization_id", organization_id).execute()
            
            contacts = contacts_result.data or []
            
            by_email = {}
            by_domain = {}
            by_name = {}  # New: name-based lookup
            prospect_names = {}
            
            for contact in contacts:
                prospect_id = contact.get("prospect_id")
                contact_id = contact.get("id")
                
                if not prospect_id:
                    continue
                
                # Store prospect name
                prospect_data = contact.get("prospects") or {}
                if prospect_id not in prospect_names:
                    prospect_names[prospect_id] = prospect_data.get("company_name", "Unknown")
                
                # Email-based lookup
                email = (contact.get("email") or "").lower().strip()
                if email:
                    by_email[email] = {
                        "prospect_id": prospect_id,
                        "contact_id": contact_id
                    }
                    
                    # Domain lookup
                    domain = self.extract_domain_from_email(email)
                    if domain:
                        if domain not in by_domain:
                            by_domain[domain] = []
                        by_domain[domain].append({
                            "prospect_id": prospect_id,
                            "contact_id": contact_id
                        })
                
                # Name-based lookup (most important!)
                # Note: contacts have a single "name" field like "Geert Menting"
                full_name = (contact.get("name") or "").strip()
                
                if full_name:
                    # Split into parts for partial matching
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""
                    
                    contact_info = {
                        "prospect_id": prospect_id,
                        "contact_id": contact_id,
                        "full_name": full_name
                    }
                    
                    # Index by normalized full name
                    norm_full = full_name.lower()
                    if norm_full not in by_name:
                        by_name[norm_full] = []
                    by_name[norm_full].append(contact_info)
                    
                    # Also index by first name (for partial matches)
                    if first_name and len(first_name) >= 3:
                        norm_first = first_name.lower()
                        if norm_first not in by_name:
                            by_name[norm_first] = []
                        by_name[norm_first].append(contact_info)
                    
                    # Also index by last name
                    if last_name and len(last_name) >= 3:
                        norm_last = last_name.lower()
                        if norm_last not in by_name:
                            by_name[norm_last] = []
                        by_name[norm_last].append(contact_info)
            
            return {
                "by_email": by_email,
                "by_domain": by_domain,
                "by_name": by_name,
                "prospect_names": prospect_names
            }
            
        except Exception as e:
            logger.error(f"Error fetching contacts for matching: {e}")
            return {"by_email": {}, "by_domain": {}, "by_name": {}, "prospect_names": {}}
    
    def calculate_contact_match(
        self,
        attendees: List[dict],
        contacts_lookup: dict
    ) -> Tuple[List[Tuple[str, float, str]], List[str]]:
        """
        Match attendees against known contacts by NAME (primary) and email (secondary).
        
        Attendees typically have: {"email": "...", "name": "Geert Menting", "is_organizer": bool}
        
        Returns:
            (matches, contact_ids) where:
            - matches: list of (prospect_id, confidence, reason) tuples
            - contact_ids: list of matched contact IDs
        """
        matches = []
        matched_contact_ids = []
        by_email = contacts_lookup.get("by_email", {})
        by_domain = contacts_lookup.get("by_domain", {})
        by_name = contacts_lookup.get("by_name", {})
        
        for attendee in attendees:
            attendee_name = (attendee.get("name") or "").strip()
            attendee_email = (attendee.get("email") or "").lower().strip()
            
            # PRIORITY 1: Name matching (most reliable since contacts are linked to prospects)
            if attendee_name and by_name:
                name_lower = attendee_name.lower()
                
                # Try exact full name match first
                if name_lower in by_name:
                    for info in by_name[name_lower]:
                        prospect_id = info["prospect_id"]
                        contact_id = info.get("contact_id")
                        
                        matches.append((
                            prospect_id,
                            self.WEIGHT_CONTACT_NAME_MATCH,
                            f"attendee name '{attendee_name}' matches contact"
                        ))
                        if contact_id and contact_id not in matched_contact_ids:
                            matched_contact_ids.append(contact_id)
                        break  # One match per attendee
                    continue  # Found name match, skip email matching
                
                # Try matching individual name parts (first or last name)
                name_parts = name_lower.split()
                for part in name_parts:
                    if len(part) >= 3 and part in by_name:  # Minimum 3 chars to avoid false positives
                        for info in by_name[part]:
                            prospect_id = info["prospect_id"]
                            contact_id = info.get("contact_id")
                            full_name = info.get("full_name", "")
                            
                            matches.append((
                                prospect_id,
                                self.WEIGHT_CONTACT_NAME_PARTIAL,
                                f"attendee name contains '{part}' matching contact '{full_name}'"
                            ))
                            if contact_id and contact_id not in matched_contact_ids:
                                matched_contact_ids.append(contact_id)
                            break  # One match per name part
                        break  # Found partial match, stop looking
            
            # PRIORITY 2: Exact email match (if we have it)
            if attendee_email and attendee_email in by_email:
                info = by_email[attendee_email]
                prospect_id = info["prospect_id"]
                contact_id = info.get("contact_id")
                
                # Only add if not already matched by name
                if contact_id not in matched_contact_ids:
                    matches.append((
                        prospect_id,
                        self.WEIGHT_CONTACT_EMAIL_EXACT,
                        f"attendee email matches contact"
                    ))
                    if contact_id:
                        matched_contact_ids.append(contact_id)
                continue
            
            # PRIORITY 3: Domain match (fallback)
            if attendee_email:
                domain = self.extract_domain_from_email(attendee_email)
                if domain and domain in by_domain:
                    for info in by_domain[domain]:
                        prospect_id = info["prospect_id"]
                        contact_id = info.get("contact_id")
                        
                        # Only add if not already matched
                        if contact_id not in matched_contact_ids:
                            matches.append((
                                prospect_id,
                                self.WEIGHT_CONTACT_DOMAIN,
                                f"attendee domain matches contact domain ({domain})"
                            ))
                            if contact_id:
                                matched_contact_ids.append(contact_id)
                        break
        
        return matches, matched_contact_ids
    
    async def match_meeting(
        self,
        meeting_id: str,
        meeting_title: str,
        attendees: List[dict],
        organization_id: str,
        contacts_lookup: dict = None,
        organizer_email: str = None
    ) -> MatchResult:
        """
        Match a single meeting to prospects in the organization.
        
        Matching strategies (in order of confidence):
        1. Attendee email matches known contact email (95%)
        2. Title contains exact company name (90%)
        3. Attendee domain matches contact domain (85%)
        4. Attendee domain matches prospect website/email (70%)
        5. Title contains partial company name (60%)
        
        Returns MatchResult with best match and all matches above threshold.
        """
        result = MatchResult(meeting_id=meeting_id)
        
        # Build complete attendees list including organizer
        all_attendees = list(attendees) if attendees else []
        
        # Also add organizer if provided separately (stored at meeting level)
        if organizer_email:
            org_email = organizer_email.lower().strip()
            # Check if organizer is already in attendees list
            existing_emails = [a.get('email', '').lower() for a in all_attendees]
            if org_email and org_email not in existing_emails:
                all_attendees.append({"email": org_email, "name": "", "is_organizer": True})
        
        # Extract emails for domain-based matching against prospects
        attendee_emails = [
            a.get('email', '').lower().strip()
            for a in all_attendees 
            if a.get('email')
        ]
        
        logger.debug(f"Matching meeting {meeting_id[:8]}... with {len(all_attendees)} attendees")
        
        try:
            # Fetch contacts lookup if not provided (for batch efficiency)
            if contacts_lookup is None:
                contacts_lookup = await self.get_contacts_for_matching(organization_id)
            
            # Fetch all prospects for organization
            prospects_result = self.supabase.table("prospects").select(
                "id, company_name, website, contact_email"
            ).eq("organization_id", organization_id).execute()
            
            prospects = prospects_result.data or []
            prospect_map = {p['id']: p for p in prospects}
            
            if not prospects and not contacts_lookup.get("by_email") and not contacts_lookup.get("by_name"):
                return result
            
            matches: List[ProspectMatch] = []
            matched_prospect_ids = set()
            
            # Strategy 1: Contact-based matching by NAME (highest priority!) and email
            contact_matches, matched_contact_ids = self.calculate_contact_match(all_attendees, contacts_lookup)
            result.matched_contact_ids = matched_contact_ids
            
            for prospect_id, confidence, reason in contact_matches:
                if prospect_id in matched_prospect_ids:
                    continue
                matched_prospect_ids.add(prospect_id)
                
                # Get company name
                company_name = contacts_lookup.get("prospect_names", {}).get(prospect_id)
                if not company_name and prospect_id in prospect_map:
                    company_name = prospect_map[prospect_id].get("company_name", "Unknown")
                
                matches.append(ProspectMatch(
                    prospect_id=prospect_id,
                    company_name=company_name or "Unknown",
                    confidence=confidence,
                    match_reason=reason
                ))
            
            # Strategy 2, 4, 5: Prospect-based matching
            for prospect in prospects:
                if prospect['id'] in matched_prospect_ids:
                    continue  # Already matched via contacts
                
                confidence = 0.0
                reasons = []
                
                # Title matching (exact or partial)
                title_score = self.calculate_title_match(
                    meeting_title, 
                    prospect.get('company_name', '')
                )
                if title_score > 0:
                    confidence = max(confidence, title_score)
                    reasons.append(f"title match ({title_score:.0%})")
                
                # Email domain matching against prospect website/email
                email_score = self.calculate_email_domain_match(
                    attendee_emails,
                    prospect.get('website'),
                    prospect.get('contact_email')
                )
                if email_score > 0:
                    confidence = max(confidence, email_score)
                    reasons.append(f"email domain match ({email_score:.0%})")
                
                # Only include if we have some confidence
                if confidence >= 0.3:
                    matches.append(ProspectMatch(
                        prospect_id=prospect['id'],
                        company_name=prospect['company_name'],
                        confidence=confidence,
                        match_reason=', '.join(reasons)
                    ))
            
            # Sort by confidence descending
            matches.sort(key=lambda m: m.confidence, reverse=True)
            
            result.all_matches = matches
            
            if matches:
                result.best_match = matches[0]
                
                # Auto-link if confidence is high enough
                if result.best_match.confidence >= self.AUTO_LINK_THRESHOLD:
                    await self._auto_link_meeting(
                        meeting_id, 
                        result.best_match.prospect_id,
                        result.best_match.confidence,
                        result.matched_contact_ids
                    )
                    result.auto_linked = True
                    contact_info = f", contacts: {len(result.matched_contact_ids)}" if result.matched_contact_ids else ""
                    logger.info(
                        f"Auto-linked meeting {meeting_id} to prospect "
                        f"{result.best_match.company_name} "
                        f"(confidence: {result.best_match.confidence:.0%}, "
                        f"reason: {result.best_match.match_reason}{contact_info})"
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"Error matching meeting {meeting_id}: {str(e)}")
            return result
    
    async def _auto_link_meeting(
        self, 
        meeting_id: str, 
        prospect_id: str, 
        confidence: float,
        contact_ids: List[str] = None
    ):
        """Auto-link a meeting to a prospect and optionally contacts."""
        try:
            update_data = {
                "prospect_id": prospect_id,
                "match_confidence": confidence,
                "prospect_link_type": "auto"
            }
            
            # Add contact_ids if provided
            if contact_ids:
                update_data["contact_ids"] = contact_ids
            
            self.supabase.table("calendar_meetings").update(
                update_data
            ).eq("id", meeting_id).execute()
        except Exception as e:
            logger.error(f"Failed to auto-link meeting {meeting_id}: {str(e)}")
    
    async def match_all_unlinked(self, organization_id: str) -> List[MatchResult]:
        """
        Match all unlinked meetings to prospects.
        
        Pre-fetches contacts lookup for efficiency when processing multiple meetings.
        """
        results = []
        
        try:
            # Pre-fetch contacts lookup (once for all meetings)
            contacts_lookup = await self.get_contacts_for_matching(organization_id)
            
            logger.debug(
                f"Contacts lookup: {len(contacts_lookup.get('by_email', {}))} emails, "
                f"{len(contacts_lookup.get('by_domain', {}))} domains"
            )
            
            # Fetch unlinked meetings (including organizer_email)
            meetings_result = self.supabase.table("calendar_meetings").select(
                "id, title, attendees, organizer_email"
            ).eq(
                "organization_id", organization_id
            ).is_(
                "prospect_id", "null"
            ).execute()
            
            meetings = meetings_result.data or []
            
            logger.info(f"Matching {len(meetings)} unlinked meetings for org {organization_id[:8]}...")
            
            for meeting in meetings:
                result = await self.match_meeting(
                    meeting_id=meeting['id'],
                    meeting_title=meeting.get('title', ''),
                    attendees=meeting.get('attendees', []),
                    organization_id=organization_id,
                    contacts_lookup=contacts_lookup,  # Reuse for efficiency
                    organizer_email=meeting.get('organizer_email')  # Include organizer!
                )
                results.append(result)
            
            # Log summary
            auto_linked = sum(1 for r in results if r.auto_linked)
            logger.info(f"Matching complete: {auto_linked}/{len(results)} auto-linked")
            
            return results
            
        except Exception as e:
            logger.error(f"Error matching unlinked meetings: {str(e)}")
            return results

