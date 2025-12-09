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
    
    def __post_init__(self):
        if self.all_matches is None:
            self.all_matches = []


class ProspectMatcher:
    """Service for matching calendar meetings to prospects."""
    
    # Minimum confidence for auto-linking
    AUTO_LINK_THRESHOLD = 0.8
    
    # Weights for different matching signals
    WEIGHT_TITLE_EXACT = 0.9
    WEIGHT_TITLE_PARTIAL = 0.6
    WEIGHT_EMAIL_DOMAIN = 0.7
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
    
    async def match_meeting(
        self,
        meeting_id: str,
        meeting_title: str,
        attendees: List[dict],
        organization_id: str
    ) -> MatchResult:
        """
        Match a single meeting to prospects in the organization.
        
        Returns MatchResult with best match and all matches above threshold.
        """
        result = MatchResult(meeting_id=meeting_id)
        
        # Extract attendee emails
        attendee_emails = [
            a.get('email', '') 
            for a in attendees 
            if a.get('email') and not a.get('is_organizer', False)
        ]
        
        try:
            # Fetch all prospects for organization
            prospects_result = self.supabase.table("prospects").select(
                "id, company_name, website, contact_email"
            ).eq("organization_id", organization_id).execute()
            
            prospects = prospects_result.data or []
            
            if not prospects:
                return result
            
            matches: List[ProspectMatch] = []
            
            for prospect in prospects:
                confidence = 0.0
                reasons = []
                
                # Title matching
                title_score = self.calculate_title_match(
                    meeting_title, 
                    prospect.get('company_name', '')
                )
                if title_score > 0:
                    confidence = max(confidence, title_score)
                    reasons.append(f"title match ({title_score:.0%})")
                
                # Email domain matching
                email_score = self.calculate_email_domain_match(
                    attendee_emails,
                    prospect.get('website'),
                    prospect.get('contact_email')
                )
                if email_score > 0:
                    # Combine scores (taking max, not sum)
                    confidence = max(confidence, email_score)
                    reasons.append(f"email domain match ({email_score:.0%})")
                
                # Only include if we have some confidence
                if confidence >= 0.3:  # Minimum threshold to consider
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
                        result.best_match.confidence
                    )
                    result.auto_linked = True
                    logger.info(
                        f"Auto-linked meeting {meeting_id} to prospect "
                        f"{result.best_match.company_name} "
                        f"(confidence: {result.best_match.confidence:.0%})"
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"Error matching meeting {meeting_id}: {str(e)}")
            return result
    
    async def _auto_link_meeting(
        self, 
        meeting_id: str, 
        prospect_id: str, 
        confidence: float
    ):
        """Auto-link a meeting to a prospect."""
        try:
            self.supabase.table("calendar_meetings").update({
                "prospect_id": prospect_id,
                "match_confidence": confidence,
                "prospect_link_type": "auto"
            }).eq("id", meeting_id).execute()
        except Exception as e:
            logger.error(f"Failed to auto-link meeting {meeting_id}: {str(e)}")
    
    async def match_all_unlinked(self, organization_id: str) -> List[MatchResult]:
        """Match all unlinked meetings to prospects."""
        results = []
        
        try:
            # Fetch unlinked meetings
            meetings_result = self.supabase.table("calendar_meetings").select(
                "id, title, attendees"
            ).eq(
                "organization_id", organization_id
            ).is_(
                "prospect_id", "null"
            ).execute()
            
            meetings = meetings_result.data or []
            
            for meeting in meetings:
                result = await self.match_meeting(
                    meeting_id=meeting['id'],
                    meeting_title=meeting.get('title', ''),
                    attendees=meeting.get('attendees', []),
                    organization_id=organization_id
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error matching unlinked meetings: {str(e)}")
            return results

