"""
Website Content Provider - Unified interface for website content extraction.

This service provides an abstraction layer for extracting content from company websites.
Primary: Neural content extraction with AI summaries and clean markdown output
Fallback: Traditional scraping with BeautifulSoup

Key features:
- Clean markdown content (no nav/footer/popups)
- AI-generated summaries tailored to company research
- JavaScript rendering support
- Automatic subpage discovery (about, team, products)
- Bot protection handling

Architecture:
- Primary provider: Neural search with get_contents API
- Fallback: Traditional HTTP scraping (website_scraper.py)
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WebsiteContent:
    """Extracted content from a company website."""
    url: str
    success: bool = False
    source: str = "unknown"  # "neural", "scraper", "fallback"
    
    # Content
    main_content: str = ""  # Clean markdown text
    summary: str = ""  # AI-generated or extracted summary
    title: str = ""
    meta_description: str = ""
    
    # Subpages
    pages_scraped: int = 0
    subpages: Dict[str, str] = field(default_factory=dict)  # page_type -> content
    
    # Structured data (if extracted)
    company_description: str = ""
    products_services: List[str] = field(default_factory=list)
    team_members: List[Dict[str, str]] = field(default_factory=list)
    contact_info: Dict[str, str] = field(default_factory=dict)
    
    # Error handling
    error: Optional[str] = None


class WebsiteContentProvider:
    """
    Unified website content extraction with intelligent fallback.
    
    Primary: Neural content extraction (handles JS, bot protection, clean output)
    Fallback: Traditional scraping (aiohttp + BeautifulSoup)
    """
    
    def __init__(self):
        """Initialize the website content provider."""
        self._client = None
        self._initialized = False
        self._fallback_scraper = None
        
        # Try to initialize neural content client
        api_key = os.getenv("EXA_API_KEY")
        if api_key:
            try:
                from exa_py import Exa
                self._client = Exa(api_key=api_key)
                self._initialized = True
                logger.info("[WEBSITE_CONTENT] Neural content provider initialized")
            except ImportError:
                logger.warning("[WEBSITE_CONTENT] Neural SDK not available")
            except Exception as e:
                logger.warning(f"[WEBSITE_CONTENT] Failed to initialize neural provider: {e}")
        else:
            logger.info("[WEBSITE_CONTENT] No API key configured, using fallback scraper only")
        
        # Always initialize fallback scraper
        try:
            from .website_scraper import get_website_scraper
            self._fallback_scraper = get_website_scraper()
            logger.info("[WEBSITE_CONTENT] Fallback scraper initialized")
        except Exception as e:
            logger.warning(f"[WEBSITE_CONTENT] Failed to initialize fallback scraper: {e}")
    
    @property
    def is_neural_available(self) -> bool:
        """Check if neural content extraction is available."""
        return self._initialized and self._client is not None
    
    async def get_website_content(
        self,
        website_url: str,
        company_name: Optional[str] = None,
        include_subpages: bool = True,
        max_subpages: int = 5
    ) -> Dict[str, Any]:
        """
        Extract content from a company website.
        
        Args:
            website_url: The company's website URL
            company_name: Company name for context-aware summaries
            include_subpages: Whether to fetch subpages (about, team, etc.)
            max_subpages: Maximum subpages to fetch
            
        Returns:
            Dictionary matching the website_scraper output format for compatibility:
            {
                "success": bool,
                "url": str,
                "pages_scraped": int,
                "summary": str,  # Markdown summary
                "content": dict,  # Optional detailed content
                "extracted_data": dict,  # Optional structured data
                "source": str,  # "neural" or "scraper"
                "error": str  # If failed
            }
        """
        if not website_url:
            return {"success": False, "error": "No website URL provided", "source": "none"}
        
        # Normalize URL
        website_url = self._normalize_url(website_url)
        
        logger.info(f"[WEBSITE_CONTENT] Extracting content from {website_url}")
        
        # Try neural extraction first
        if self.is_neural_available:
            try:
                result = await self._extract_neural(
                    website_url, company_name, include_subpages, max_subpages
                )
                if result.get("success"):
                    logger.info(
                        f"[WEBSITE_CONTENT] Neural extraction successful: "
                        f"{result.get('pages_scraped', 0)} pages"
                    )
                    return result
                else:
                    logger.warning(
                        f"[WEBSITE_CONTENT] Neural extraction failed: {result.get('error')}, "
                        f"falling back to scraper"
                    )
            except Exception as e:
                logger.warning(f"[WEBSITE_CONTENT] Neural extraction error: {e}, falling back")
        
        # Fallback to traditional scraping
        if self._fallback_scraper:
            try:
                result = await self._extract_fallback(website_url, max_subpages)
                if result.get("success"):
                    logger.info(
                        f"[WEBSITE_CONTENT] Fallback scraper successful: "
                        f"{result.get('pages_scraped', 0)} pages"
                    )
                return result
            except Exception as e:
                logger.error(f"[WEBSITE_CONTENT] Fallback scraper error: {e}")
                return {
                    "success": False,
                    "url": website_url,
                    "error": str(e),
                    "source": "fallback_error"
                }
        
        return {
            "success": False,
            "url": website_url,
            "error": "No content extraction method available",
            "source": "none"
        }
    
    async def _extract_neural(
        self,
        website_url: str,
        company_name: Optional[str],
        include_subpages: bool,
        max_subpages: int
    ) -> Dict[str, Any]:
        """
        Extract content using neural content API.
        
        Features:
        - Clean markdown output (no nav/footer/ads)
        - AI-generated summaries
        - JavaScript rendering
        - Automatic subpage discovery
        """
        if not self._client:
            return {"success": False, "error": "Neural client not initialized"}
        
        try:
            loop = asyncio.get_event_loop()
            
            # Build query for summary generation
            summary_query = "company description products services team leadership about"
            if company_name:
                summary_query = f"{company_name} {summary_query}"
            
            # Subpage targets for company research
            subpage_targets = [
                "about", "over-ons", "company", "team", "leadership",
                "products", "services", "diensten", "contact"
            ]
            
            def do_get_contents():
                # Note: highlights feature was removed from Python SDK
                # Use summary instead for AI-generated insights
                params = {
                    "urls": [website_url],
                    "text": {"max_characters": 8000},  # Main content
                    "summary": {"query": summary_query},  # AI summary
                    "livecrawl": "fallback"  # Use cache first, crawl if needed
                }
                
                # Add subpage crawling if requested
                if include_subpages:
                    params["subpages"] = max_subpages
                    params["subpage_target"] = " ".join(subpage_targets)
                
                return self._client.get_contents(**params)
            
            response = await loop.run_in_executor(None, do_get_contents)
            
            if not response.results:
                return {
                    "success": False,
                    "url": website_url,
                    "error": "No content returned",
                    "source": "neural"
                }
            
            # Process results
            main_result = response.results[0]
            
            # Extract content
            main_content = getattr(main_result, 'text', '') or ''
            ai_summary = getattr(main_result, 'summary', '') or ''
            title = getattr(main_result, 'title', '') or ''
            
            # Count pages (main + subpages)
            pages_scraped = len(response.results)
            
            # Process subpages
            subpages_content = {}
            for i, result in enumerate(response.results):
                page_url = getattr(result, 'url', '')
                page_text = getattr(result, 'text', '')
                if page_text and i > 0:  # Skip main page
                    page_type = self._classify_url(page_url)
                    if page_type not in subpages_content:
                        subpages_content[page_type] = page_text
            
            # Build comprehensive summary for Claude
            summary_parts = []
            summary_parts.append(f"## Website Content Summary (Neural Extraction)")
            summary_parts.append(f"**URL**: {website_url}")
            summary_parts.append(f"**Pages Analyzed**: {pages_scraped}")
            summary_parts.append("")
            
            if title:
                summary_parts.append(f"**Title**: {title}")
                summary_parts.append("")
            
            if ai_summary:
                summary_parts.append("### AI-Generated Summary")
                summary_parts.append(ai_summary)
                summary_parts.append("")
            
            if main_content:
                summary_parts.append("### Main Content")
                # Truncate for summary but keep meaningful amount
                content_preview = main_content[:3000]
                if len(main_content) > 3000:
                    content_preview += "\n\n*[Content truncated for summary]*"
                summary_parts.append(content_preview)
                summary_parts.append("")
            
            # Add subpage summaries
            for page_type, content in subpages_content.items():
                summary_parts.append(f"### {page_type.title()} Page")
                content_preview = content[:1500]
                if len(content) > 1500:
                    content_preview += "\n\n*[Truncated]*"
                summary_parts.append(content_preview)
                summary_parts.append("")
            
            return {
                "success": True,
                "url": website_url,
                "source": "neural",
                "pages_scraped": pages_scraped,
                "summary": "\n".join(summary_parts),
                "content": {
                    "main": {
                        "url": website_url,
                        "title": title,
                        "text": main_content,
                        "summary": ai_summary
                    },
                    **{pt: {"text": txt} for pt, txt in subpages_content.items()}
                },
                "extracted_data": {
                    "ai_summary": ai_summary,
                    "title": title
                }
            }
            
        except Exception as e:
            logger.error(f"[WEBSITE_CONTENT] Neural extraction error: {e}")
            return {
                "success": False,
                "url": website_url,
                "error": str(e),
                "source": "neural_error"
            }
    
    async def _extract_fallback(
        self,
        website_url: str,
        max_pages: int
    ) -> Dict[str, Any]:
        """
        Extract content using fallback scraper.
        
        Uses the existing website_scraper.py for traditional HTTP scraping.
        """
        if not self._fallback_scraper:
            return {
                "success": False,
                "url": website_url,
                "error": "Fallback scraper not available",
                "source": "fallback"
            }
        
        try:
            result = await self._fallback_scraper.scrape_website(
                website_url,
                max_pages=max_pages
            )
            
            # Add source marker
            result["source"] = "scraper"
            
            return result
            
        except Exception as e:
            logger.error(f"[WEBSITE_CONTENT] Fallback extraction error: {e}")
            return {
                "success": False,
                "url": website_url,
                "error": str(e),
                "source": "fallback_error"
            }
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure it has a scheme."""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url.rstrip("/")
    
    def _classify_url(self, url: str) -> str:
        """Classify page type based on URL."""
        url_lower = url.lower()
        
        classifications = [
            (["about", "over-ons", "company", "bedrijf"], "about"),
            (["product", "service", "dienst", "solution", "oplossing"], "products"),
            (["team", "leadership", "management", "mensen"], "team"),
            (["contact"], "contact"),
            (["news", "nieuws", "blog", "press"], "news"),
            (["career", "job", "vacature"], "careers"),
        ]
        
        for keywords, page_type in classifications:
            if any(kw in url_lower for kw in keywords):
                return page_type
        
        return "other"
    
    # Compatibility method - matches website_scraper interface
    async def scrape_website(
        self,
        website_url: str,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Compatibility method matching website_scraper.scrape_website interface.
        
        This allows the provider to be used as a drop-in replacement.
        """
        return await self.get_website_content(
            website_url=website_url,
            include_subpages=True,
            max_subpages=max_pages or 5
        )


# Singleton instance
_provider: Optional[WebsiteContentProvider] = None


def get_website_content_provider() -> WebsiteContentProvider:
    """Get or create the WebsiteContentProvider singleton."""
    global _provider
    if _provider is None:
        _provider = WebsiteContentProvider()
    return _provider
