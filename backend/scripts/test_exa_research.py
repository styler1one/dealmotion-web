#!/usr/bin/env python3
"""
Test script for Exa-First Research Architecture (V2).

This script tests the Exa Research Service with sample companies
to validate output quality before production rollout.

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

from app.services.exa_research_service import get_exa_research_service

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
        "linkedin_url": "https://www.linkedin.com/company/adyen",
        "website_url": "https://www.adyen.com",
        "expected": {
            "industry": "payments",
            "ceo": "Pieter van der Does",
        }
    },
    {
        "name": "Booking.com",
        "country": "Netherlands",
        "linkedin_url": "https://www.linkedin.com/company/booking.com",
        "website_url": "https://www.booking.com",
        "expected": {
            "industry": "travel",
        }
    },
    {
        "name": "Stripe",
        "country": "United States",
        "linkedin_url": "https://www.linkedin.com/company/stripe",
        "website_url": "https://stripe.com",
        "expected": {
            "industry": "fintech",
            "ceo": "Patrick Collison",
        }
    },
    {
        "name": "Notion",
        "country": "United States",
        "linkedin_url": "https://www.linkedin.com/company/notionhq",
        "website_url": "https://www.notion.so",
        "expected": {
            "industry": "productivity",
        }
    },
    {
        "name": "Miro",
        "country": "Netherlands",
        "linkedin_url": "https://www.linkedin.com/company/maboradio",
        "website_url": "https://miro.com",
        "expected": {
            "industry": "collaboration",
        }
    },
]


async def test_company(service, company: dict) -> dict:
    """Test research for a single company."""
    name = company["name"]
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {name}")
    logger.info(f"{'='*60}")
    
    start_time = datetime.now()
    
    try:
        result = await service.research_company(
            company_name=name,
            country=company.get("country"),
            linkedin_url=company.get("linkedin_url"),
            website_url=company.get("website_url"),
            model="exa-research",  # Use standard model for testing
            max_wait_seconds=180
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Evaluate results
        evaluation = {
            "company": name,
            "success": result.success,
            "elapsed_seconds": elapsed,
            "cost_dollars": result.cost_dollars,
            "c_suite_count": len(result.c_suite),
            "senior_leadership_count": len(result.senior_leadership),
            "board_count": len(result.board_of_directors),
            "funding_rounds_count": len(result.funding_rounds),
            "news_count": len(result.recent_news),
            "errors": result.errors,
        }
        
        if result.success:
            # Print summary
            logger.info(f"\n✅ SUCCESS in {elapsed:.1f}s (${result.cost_dollars:.4f})")
            logger.info(f"   Company: {result.company_name or result.legal_name}")
            logger.info(f"   Industry: {result.industry}")
            logger.info(f"   Employees: {result.employee_range}")
            logger.info(f"   C-Suite: {len(result.c_suite)} executives")
            for exec in result.c_suite[:3]:
                logger.info(f"      - {exec.name}: {exec.title}")
            logger.info(f"   Senior Leadership: {len(result.senior_leadership)} people")
            logger.info(f"   Board: {len(result.board_of_directors)} members")
            logger.info(f"   Funding: {result.total_funding_raised}")
            logger.info(f"   Funding Rounds: {len(result.funding_rounds)}")
            logger.info(f"   Recent News: {len(result.recent_news)} items")
            logger.info(f"   Competitors: {', '.join(result.main_competitors[:3])}")
            
            # Check expected values
            expected = company.get("expected", {})
            if expected:
                logger.info("\n   Expected value checks:")
                for key, value in expected.items():
                    actual = getattr(result, key, None)
                    if actual and value.lower() in str(actual).lower():
                        logger.info(f"      ✓ {key}: found '{value}'")
                        evaluation[f"check_{key}"] = True
                    else:
                        logger.warning(f"      ✗ {key}: expected '{value}', got '{actual}'")
                        evaluation[f"check_{key}"] = False
        else:
            logger.error(f"\n❌ FAILED: {', '.join(result.errors)}")
        
        return evaluation
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ ERROR after {elapsed:.1f}s: {e}")
        return {
            "company": name,
            "success": False,
            "elapsed_seconds": elapsed,
            "error": str(e)
        }


async def main():
    """Run tests for all companies."""
    logger.info("="*60)
    logger.info("Exa-First Research Architecture (V2) Test Suite")
    logger.info("="*60)
    
    # Check API key
    if not os.getenv("EXA_API_KEY"):
        logger.error("EXA_API_KEY environment variable not set!")
        sys.exit(1)
    
    service = get_exa_research_service()
    if not service.is_available:
        logger.error("Exa Research Service not available!")
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
    total_cost = sum(r.get("cost_dollars", 0) for r in results)
    avg_time = sum(r.get("elapsed_seconds", 0) for r in results) / len(results)
    
    logger.info(f"\nResults: {success_count}/{len(results)} successful")
    logger.info(f"Total cost: ${total_cost:.4f}")
    logger.info(f"Average time: {avg_time:.1f}s")
    
    # Quality metrics
    total_c_suite = sum(r.get("c_suite_count", 0) for r in results)
    total_leadership = sum(r.get("senior_leadership_count", 0) for r in results)
    total_news = sum(r.get("news_count", 0) for r in results)
    
    logger.info(f"\nData quality:")
    logger.info(f"  Total C-Suite found: {total_c_suite}")
    logger.info(f"  Total Senior Leadership: {total_leadership}")
    logger.info(f"  Total News items: {total_news}")
    
    # Individual results
    logger.info("\nPer-company results:")
    for r in results:
        status = "✅" if r.get("success") else "❌"
        cost = r.get("cost_dollars", 0)
        time = r.get("elapsed_seconds", 0)
        c_suite = r.get("c_suite_count", 0)
        logger.info(f"  {status} {r['company']}: {time:.1f}s, ${cost:.4f}, {c_suite} C-suite")
    
    # Return exit code
    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
