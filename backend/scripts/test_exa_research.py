#!/usr/bin/env python3
"""
Test script for Exa Comprehensive Research Architecture (V2).

This script tests the Exa Comprehensive Researcher with sample companies
to validate output quality before production rollout.

The new architecture uses 30 parallel searches for state-of-the-art coverage:
- COMPANY (4): identity, business model, products, financials
- PEOPLE (6): CEO, C-suite, leadership, board, changes, founder
- MARKET (5): news, partnerships, hiring, tech, competition
- DEEP INSIGHTS (7): reviews, events, awards, media, customers, challenges
- STRATEGIC (6): key accounts, risks, roadmap, ESG, patents, vendors
- LOCAL (2): country-specific media and rankings

Usage:
    python scripts/test_exa_research.py

Environment:
    EXA_API_KEY: Required - Exa API key
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.exa_research_service import get_exa_comprehensive_researcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test companies - mix of sizes, industries, and regions
TEST_COMPANIES = [
    {
        "name": "Adyen",
        "country": "Netherlands",
        "city": "Amsterdam",
        "linkedin_url": "https://www.linkedin.com/company/adyen",
        "website_url": "https://www.adyen.com",
    },
    {
        "name": "Booking.com",
        "country": "Netherlands",
        "city": "Amsterdam",
        "linkedin_url": "https://www.linkedin.com/company/booking.com",
        "website_url": "https://www.booking.com",
    },
    {
        "name": "Stripe",
        "country": "United States",
        "city": "San Francisco",
        "linkedin_url": "https://www.linkedin.com/company/stripe",
        "website_url": "https://stripe.com",
    },
    {
        "name": "Notion",
        "country": "United States",
        "city": "San Francisco",
        "linkedin_url": "https://www.linkedin.com/company/notionhq",
        "website_url": "https://www.notion.so",
    },
    {
        "name": "Miro",
        "country": "Netherlands",
        "city": "Amsterdam",
        "linkedin_url": "https://www.linkedin.com/company/miroboard",
        "website_url": "https://miro.com",
    },
]


async def test_company(service, company: dict) -> dict:
    """Test research for a single company."""
    name = company["name"]
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {name} ({company.get('country', 'Unknown')})")
    logger.info(f"{'='*60}")
    
    start_time = datetime.now()
    
    try:
        result = await service.research_company(
            company_name=name,
            country=company.get("country"),
            city=company.get("city"),
            linkedin_url=company.get("linkedin_url"),
            website_url=company.get("website_url"),
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Evaluation based on new ComprehensiveResearchResult
        evaluation = {
            "company": name,
            "country": company.get("country", "Unknown"),
            "success": result.success,
            "elapsed_seconds": elapsed,
            "topics_completed": result.topics_completed,
            "topics_failed": result.topics_failed,
            "total_results": result.total_results,
            "errors": result.errors,
        }
        
        if result.success:
            # Print summary
            success_rate = result.topics_completed / (result.topics_completed + result.topics_failed) * 100
            logger.info(f"\n✅ SUCCESS in {elapsed:.1f}s")
            logger.info(f"   Topics: {result.topics_completed}/{result.topics_completed + result.topics_failed} ({success_rate:.0f}%)")
            logger.info(f"   Total Results: {result.total_results}")
            
            # Show per-section breakdown
            sections = {
                "COMPANY": ["company_identity", "business_model", "products_services", "financials_funding"],
                "PEOPLE": ["ceo_founder", "c_suite", "senior_leadership", "board_advisors", "leadership_changes", "founder_story"],
                "MARKET": ["recent_news", "partnerships_acquisitions", "hiring_signals", "technology_stack", "competition"],
                "DEEP INSIGHTS": ["employee_reviews", "events_speaking", "awards_recognition", "media_interviews", "customer_reviews", "challenges_priorities", "certifications"],
                "STRATEGIC": ["key_customers", "risk_signals", "future_roadmap", "sustainability_esg", "patents_innovation", "vendor_partners"],
                "LOCAL": ["local_media", "local_rankings"],
            }
            
            logger.info("\n   Section breakdown:")
            for section_name, topics in sections.items():
                section_results = 0
                section_success = 0
                for topic in topics:
                    if topic in result.topic_results:
                        topic_result = result.topic_results[topic]
                        section_results += topic_result.results_count
                        if topic_result.success:
                            section_success += 1
                logger.info(f"      {section_name}: {section_success}/{len(topics)} topics, {section_results} results")
            
            # Show markdown preview
            if result.markdown_output:
                preview = result.markdown_output[:500] + "..." if len(result.markdown_output) > 500 else result.markdown_output
                logger.info(f"\n   Markdown preview ({len(result.markdown_output)} chars):")
                for line in preview.split('\n')[:10]:
                    logger.info(f"      {line}")
        else:
            logger.error(f"\n❌ FAILED: {', '.join(result.errors) if result.errors else 'Unknown error'}")
        
        return evaluation
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ ERROR after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return {
            "company": name,
            "success": False,
            "elapsed_seconds": elapsed,
            "error": str(e)
        }


async def main():
    """Run tests for all companies."""
    logger.info("="*60)
    logger.info("Exa Comprehensive Research Architecture (V2) Test Suite")
    logger.info("30 Parallel Searches per Company")
    logger.info("="*60)
    
    # Check API key
    if not os.getenv("EXA_API_KEY"):
        logger.error("EXA_API_KEY environment variable not set!")
        sys.exit(1)
    
    service = get_exa_comprehensive_researcher()
    if not service.is_available:
        logger.error("Exa Comprehensive Researcher not available!")
        sys.exit(1)
    
    logger.info(f"Testing {len(TEST_COMPANIES)} companies...")
    
    results = []
    for company in TEST_COMPANIES:
        result = await test_company(service, company)
        results.append(result)
        # Small delay between tests to be nice to the API
        await asyncio.sleep(2)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    success_count = sum(1 for r in results if r.get("success"))
    avg_time = sum(r.get("elapsed_seconds", 0) for r in results) / len(results) if results else 0
    total_results = sum(r.get("total_results", 0) for r in results)
    total_topics = sum(r.get("topics_completed", 0) for r in results)
    
    logger.info(f"\nResults: {success_count}/{len(results)} successful")
    logger.info(f"Average time: {avg_time:.1f}s")
    logger.info(f"Total topics completed: {total_topics}")
    logger.info(f"Total search results: {total_results}")
    
    # Individual results
    logger.info("\nPer-company results:")
    for r in results:
        status = "✅" if r.get("success") else "❌"
        time = r.get("elapsed_seconds", 0)
        topics = r.get("topics_completed", 0)
        total = r.get("total_results", 0)
        logger.info(f"  {status} {r['company']} ({r.get('country', 'Unknown')}): {time:.1f}s, {topics} topics, {total} results")
    
    # Errors summary
    all_errors = []
    for r in results:
        if r.get("errors"):
            for e in r["errors"]:
                all_errors.append(f"{r['company']}: {e}")
        if r.get("error"):
            all_errors.append(f"{r['company']}: {r['error']}")
    
    if all_errors:
        logger.info("\nErrors encountered:")
        for e in all_errors[:10]:  # Limit to first 10
            logger.info(f"  ⚠️ {e}")
    
    # Return exit code
    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
