"""
Website Scraper Service

Scrapes company websites to extract relevant information for research.
Focuses on key pages: homepage, about, products/services, team, contact.
"""

import os
import re
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class WebsiteScraper:
    """
    Scrapes company websites to extract structured information.
    
    Key features:
    - Async HTTP requests for performance
    - Smart page discovery (about, products, team, etc.)
    - Text extraction and cleaning
    - Rate limiting to be respectful
    """
    
    def __init__(self):
        """Initialize scraper with default settings."""
        # Faster timeouts - 10s total, 5s per connection
        self.timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_read=5)
        self.max_pages = 5  # Reduced for faster results
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5,nl;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        # Pages to look for
        self.important_paths = [
            "/", "/about", "/about-us", "/over-ons", "/company",
            "/products", "/services", "/diensten", "/solutions", "/oplossingen",
            "/team", "/leadership", "/management", "/our-team",
            "/contact", "/contact-us", "/contacteer-ons",
            "/news", "/blog", "/nieuws", "/press",
            "/careers", "/jobs", "/vacatures",
            "/customers", "/clients", "/case-studies", "/klanten",
        ]
    
    async def scrape_website(
        self,
        website_url: str,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape a company website and extract structured information.
        
        Args:
            website_url: The company's website URL
            max_pages: Maximum pages to scrape (default: self.max_pages)
            
        Returns:
            Dictionary with extracted website content
        """
        if not website_url:
            return {"success": False, "error": "No website URL provided"}
        
        # Normalize URL
        website_url = self._normalize_url(website_url)
        base_domain = urlparse(website_url).netloc
        
        if max_pages is None:
            max_pages = self.max_pages
        
        result = {
            "source": "website_scraper",
            "url": website_url,
            "success": False,
            "pages_scraped": 0,
            "content": {},
            "extracted_data": {
                "company_description": "",
                "products_services": [],
                "team_members": [],
                "contact_info": {},
                "recent_news": [],
                "key_facts": []
            }
        }
        
        # Create connector with force_close to prevent unclosed session warnings
        connector = aiohttp.TCPConnector(force_close=True, limit=10)
        session = None
        
        try:
            session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.headers,
                connector=connector
            )
            
            # First, scrape the homepage
            homepage_content = await self._fetch_page(session, website_url)
            if homepage_content:
                result["content"]["homepage"] = homepage_content
                result["pages_scraped"] += 1
                
                # Find important links from homepage
                discovered_urls = self._discover_important_urls(
                    homepage_content["html"],
                    website_url,
                    base_domain
                )
            else:
                # Homepage failed, try common paths directly
                discovered_urls = [
                    urljoin(website_url, path) 
                    for path in self.important_paths[1:]  # Skip "/"
                ]
            
            # Scrape discovered pages (with limit)
            pages_to_scrape = discovered_urls[:max_pages - 1]
            
            for url in pages_to_scrape:
                if result["pages_scraped"] >= max_pages:
                    break
                
                page_content = await self._fetch_page(session, url)
                if page_content:
                    page_type = self._classify_page(url, page_content)
                    result["content"][page_type] = page_content
                    result["pages_scraped"] += 1
                
                # Small delay to be respectful
                await asyncio.sleep(0.5)
            
            # Extract structured data from all scraped content
            result["extracted_data"] = self._extract_structured_data(
                result["content"]
            )
            
            # Generate summary
            result["summary"] = self._generate_summary(result)
            result["success"] = result["pages_scraped"] > 0
                
        except Exception as e:
            logger.error(f"Error scraping website {website_url}: {e}")
            result["error"] = str(e)
        
        finally:
            # Explicitly close the session to prevent "Unclosed client session" warnings
            if session is not None:
                await session.close()
            # Also close the connector
            if connector is not None:
                await connector.close()
        
        return result
    
    async def _fetch_page(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single page."""
        try:
            async with session.get(url, allow_redirects=True, ssl=False) as response:
                # Fast fail on non-200 status
                if response.status != 200:
                    logger.debug(f"Non-200 status {response.status} for {url}")
                    return None
                
                # Check content type
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    return None
                
                # Check for Cloudflare/bot protection in headers
                server = response.headers.get("Server", "").lower()
                if "cloudflare" in server:
                    logger.debug(f"Cloudflare detected for {url}, skipping")
                    return None
                
                html = await response.text()
                
                # Quick check for bot protection pages
                if any(block in html.lower() for block in [
                    "just a moment", "checking your browser", 
                    "enable javascript", "access denied",
                    "captcha", "blocked", "rate limit"
                ]):
                    logger.debug(f"Bot protection detected for {url}")
                    return None
                
                soup = BeautifulSoup(html, "html.parser")
                
                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                
                # Extract text
                text = soup.get_text(separator="\n", strip=True)
                text = self._clean_text(text)
                
                # Extract title
                title = soup.title.string if soup.title else ""
                
                # Extract meta description
                meta_desc = ""
                meta_tag = soup.find("meta", attrs={"name": "description"})
                if meta_tag:
                    meta_desc = meta_tag.get("content", "")
                
                return {
                    "url": str(response.url),
                    "title": title,
                    "meta_description": meta_desc,
                    "text": text[:10000],  # Limit text length
                    "html": html[:50000]  # Keep some HTML for link discovery
                }
                
        except asyncio.TimeoutError:
            logger.debug(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure it has a scheme."""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # Remove trailing slash for consistency
        return url.rstrip("/")
    
    def _discover_important_urls(
        self,
        html: str,
        base_url: str,
        base_domain: str
    ) -> List[str]:
        """Find important pages from homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        found_urls = set()
        
        # Keywords that indicate important pages
        keywords = [
            "about", "over", "company", "bedrijf",
            "product", "service", "dienst", "solution", "oplossing",
            "team", "leadership", "management", "mensen",
            "contact", "news", "nieuws", "blog", "press",
            "customer", "client", "case", "klant",
            "career", "job", "vacature", "werk"
        ]
        
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()
            
            # Skip external links, anchors, javascript, etc.
            if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            
            # Make absolute URL
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Only same domain
            if parsed.netloc != base_domain:
                continue
            
            # Check if URL or link text contains important keywords
            href_lower = href.lower()
            if any(kw in href_lower or kw in text for kw in keywords):
                found_urls.add(full_url)
        
        # Also try common paths that might not be linked
        for path in self.important_paths:
            found_urls.add(urljoin(base_url, path))
        
        return list(found_urls)[:20]  # Limit discovery
    
    def _classify_page(self, url: str, content: Dict[str, Any]) -> str:
        """Classify page type based on URL and content."""
        url_lower = url.lower()
        title_lower = (content.get("title") or "").lower()
        
        classifications = [
            (["about", "over-ons", "company", "bedrijf"], "about"),
            (["product", "service", "dienst", "solution", "oplossing"], "products"),
            (["team", "leadership", "management", "mensen"], "team"),
            (["contact"], "contact"),
            (["news", "nieuws", "blog", "press"], "news"),
            (["career", "job", "vacature"], "careers"),
            (["customer", "client", "case", "klant"], "customers"),
        ]
        
        for keywords, page_type in classifications:
            if any(kw in url_lower or kw in title_lower for kw in keywords):
                return page_type
        
        return "other"
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        # Remove very short lines (likely menu items)
        lines = text.split('\n')
        lines = [l.strip() for l in lines if len(l.strip()) > 20 or l.strip() == '']
        return '\n'.join(lines)
    
    def _extract_structured_data(
        self,
        content: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract structured data from scraped content."""
        data = {
            "company_description": "",
            "products_services": [],
            "team_members": [],
            "contact_info": {},
            "recent_news": [],
            "key_facts": []
        }
        
        # Extract company description from about page or homepage
        for page_type in ["about", "homepage"]:
            if page_type in content:
                page = content[page_type]
                desc = page.get("meta_description", "")
                if not desc:
                    # Take first paragraph-like text
                    text = page.get("text", "")
                    paragraphs = [p for p in text.split('\n\n') if len(p) > 100]
                    if paragraphs:
                        desc = paragraphs[0][:500]
                if desc:
                    data["company_description"] = desc
                    break
        
        # Extract contact info
        if "contact" in content:
            text = content["contact"].get("text", "")
            # Simple email extraction
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
            if emails:
                data["contact_info"]["email"] = emails[0]
            # Simple phone extraction
            phones = re.findall(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', text)
            if phones:
                data["contact_info"]["phone"] = phones[0]
        
        # Extract products/services
        if "products" in content:
            text = content["products"].get("text", "")
            # Simple extraction - take first few bullet-point-like items
            lines = [l.strip() for l in text.split('\n') if 20 < len(l.strip()) < 200]
            data["products_services"] = lines[:10]
        
        # Extract team members from team/leadership pages
        for page_type in ["team", "about"]:
            if page_type in content:
                html = content[page_type].get("html", "")
                text = content[page_type].get("text", "")
                team_members = self._extract_team_members(html, text)
                if team_members:
                    data["team_members"] = team_members
                    break
        
        return data
    
    def _extract_team_members(
        self,
        html: str,
        text: str
    ) -> List[Dict[str, str]]:
        """
        Extract team member names and titles from team/about pages.
        
        Looks for common patterns:
        - Name + Title in close proximity
        - Structured team sections
        - LinkedIn URLs associated with names
        """
        team_members = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Common title patterns (Dutch and English)
        title_patterns = [
            r"CEO", r"CFO", r"CTO", r"COO", r"CMO", r"CHRO", r"CIO",
            r"Chief\s+\w+\s+Officer", r"Managing\s+Director", r"General\s+Manager",
            r"Founder", r"Co-?[Ff]ounder", r"Owner", r"Partner",
            r"Director", r"VP", r"Vice\s+President", r"Head\s+of",
            r"Manager", r"Lead", r"Senior", 
            r"Directeur", r"Eigenaar", r"Oprichter", r"Mede-?oprichter",
            r"Algemeen\s+Directeur", r"Commercieel\s+Directeur",
        ]
        title_regex = re.compile("|".join(title_patterns), re.IGNORECASE)
        
        # Method 1: Look for team cards (common website pattern)
        team_cards = soup.find_all(class_=re.compile(
            r'team|member|person|employee|staff|leadership|executive|director',
            re.IGNORECASE
        ))
        
        for card in team_cards[:20]:  # Limit to prevent too many
            # Look for name (usually in h2, h3, h4, or strong tag)
            name_elem = card.find(['h2', 'h3', 'h4', 'h5', 'strong', 'b'])
            if name_elem:
                name = name_elem.get_text(strip=True)
                # Validate it looks like a name (2-4 words, each capitalized)
                if 2 <= len(name.split()) <= 5 and name[0].isupper():
                    member = {"name": name}
                    
                    # Look for title nearby
                    title_elem = card.find(string=title_regex)
                    if title_elem:
                        member["title"] = title_elem.strip()
                    else:
                        # Try next sibling or parent's text
                        card_text = card.get_text(separator=" ", strip=True)
                        title_match = title_regex.search(card_text)
                        if title_match:
                            # Get surrounding context for title
                            start = max(0, title_match.start() - 5)
                            end = min(len(card_text), title_match.end() + 30)
                            member["title"] = card_text[start:end].strip()
                    
                    # Look for LinkedIn URL
                    linkedin_link = card.find('a', href=re.compile(r'linkedin\.com/in/', re.IGNORECASE))
                    if linkedin_link:
                        member["linkedin"] = linkedin_link.get('href')
                    
                    if member not in team_members:
                        team_members.append(member)
        
        # Method 2: If no cards found, look for name + title patterns in text
        if not team_members:
            # Pattern: "Name Name - Title" or "Name Name, Title"
            name_title_pattern = re.compile(
                r'([A-Z][a-z]+(?:\s+(?:van|de|der|den|het|[A-Z][a-z]+))+)\s*[-–,]\s*(' + 
                '|'.join(title_patterns) + r'[^.]*)',
                re.IGNORECASE
            )
            
            for match in name_title_pattern.finditer(text):
                name = match.group(1).strip()
                title = match.group(2).strip()
                if 2 <= len(name.split()) <= 5:
                    member = {"name": name, "title": title}
                    if member not in team_members:
                        team_members.append(member)
        
        # Limit results and clean up
        return team_members[:15]  # Max 15 team members
    
    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate a text summary of scraped content."""
        parts = []
        
        parts.append(f"## Website Content Summary")
        parts.append(f"**URL**: {result['url']}")
        parts.append(f"**Pages Scraped**: {result['pages_scraped']}")
        parts.append("")
        
        # Add content from each page
        for page_type, content in result.get("content", {}).items():
            if content and content.get("text"):
                parts.append(f"### {page_type.title()} Page")
                if content.get("title"):
                    parts.append(f"**Title**: {content['title']}")
                if content.get("meta_description"):
                    parts.append(f"**Description**: {content['meta_description']}")
                # Add truncated text
                text = content["text"][:2000]
                if len(content["text"]) > 2000:
                    text += "..."
                parts.append(f"\n{text}\n")
        
        return "\n".join(parts)


# Lazy singleton
_website_scraper: Optional[WebsiteScraper] = None

def get_website_scraper() -> WebsiteScraper:
    """Get or create website scraper instance."""
    global _website_scraper
    if _website_scraper is None:
        _website_scraper = WebsiteScraper()
    return _website_scraper

