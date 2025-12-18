#!/usr/bin/env python3
"""
Test Exa Research for a single company.

Usage:
    python scripts/test_single_company.py "Company Name" [--country "Netherlands"] [--model "exa-research-pro"]

Example:
    python scripts/test_single_company.py "Adyen" --country "Netherlands"
    python scripts/test_single_company.py "Stripe" --model "exa-research-pro"
"""

import os
import sys
import asyncio
import argparse
import logging
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.exa_research_service import get_exa_research_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_company(
    company_name: str,
    country: str = None,
    linkedin_url: str = None,
    website_url: str = None,
    model: str = "exa-research",
    output_file: str = None
):
    """Test research for a single company."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {company_name}")
    if country:
        logger.info(f"Country: {country}")
    logger.info(f"Model: {model}")
    logger.info(f"{'='*60}\n")
    
    # Check API key
    if not os.getenv("EXA_API_KEY"):
        logger.error("EXA_API_KEY environment variable not set!")
        return
    
    service = get_exa_research_service()
    if not service.is_available:
        logger.error("Exa Research Service not available!")
        return
    
    start_time = datetime.now()
    
    result = await service.research_company(
        company_name=company_name,
        country=country,
        linkedin_url=linkedin_url,
        website_url=website_url,
        model=model,
        max_wait_seconds=180
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if result.success:
        logger.info(f"✅ SUCCESS in {elapsed:.1f}s")
        logger.info(f"Cost: ${result.cost_dollars:.4f}")
        logger.info(f"Searches: {result.num_searches}, Pages: {result.num_pages}")
        
        logger.info(f"\n--- Company Info ---")
        logger.info(f"Name: {result.company_name or result.legal_name}")
        logger.info(f"Trading Name: {result.trading_name}")
        logger.info(f"Industry: {result.industry}")
        logger.info(f"Sub-sector: {result.sub_sector}")
        logger.info(f"Founded: {result.founded}")
        logger.info(f"Headquarters: {result.headquarters}")
        logger.info(f"Employees: {result.employee_range}")
        logger.info(f"Revenue: {result.revenue_estimate}")
        logger.info(f"Website: {result.website}")
        logger.info(f"LinkedIn: {result.linkedin_url}")
        
        logger.info(f"\n--- Leadership ({len(result.c_suite)} C-Suite, {len(result.senior_leadership)} Senior) ---")
        for exec in result.c_suite:
            founder = " (Founder)" if exec.is_founder else ""
            logger.info(f"  C-Suite: {exec.name} - {exec.title}{founder}")
            if exec.linkedin_url:
                logger.info(f"           {exec.linkedin_url}")
        for exec in result.senior_leadership[:5]:
            logger.info(f"  Senior: {exec.name} - {exec.title} ({exec.department})")
        
        if result.board_of_directors:
            logger.info(f"\n--- Board of Directors ({len(result.board_of_directors)}) ---")
            for member in result.board_of_directors:
                logger.info(f"  {member.get('name', '')} - {member.get('role', '')} ({member.get('affiliation', '')})")
        
        logger.info(f"\n--- Funding ---")
        logger.info(f"Ownership: {result.ownership_type}")
        logger.info(f"Total Raised: {result.total_funding_raised}")
        for round in result.funding_rounds:
            logger.info(f"  {round.date}: {round.round_type} - {round.amount} (Lead: {round.lead_investor})")
        
        if result.recent_news:
            logger.info(f"\n--- Recent News ({len(result.recent_news)}) ---")
            for news in result.recent_news[:5]:
                logger.info(f"  {news.date}: {news.headline}")
        
        logger.info(f"\n--- Signals ---")
        logger.info(f"Job Openings: {result.job_openings_count}")
        logger.info(f"Hiring Velocity: {result.hiring_velocity}")
        if result.top_hiring_departments:
            logger.info(f"Top Departments: {', '.join(result.top_hiring_departments)}")
        if result.growth_signals:
            logger.info(f"Growth Signals:")
            for signal in result.growth_signals:
                logger.info(f"  - {signal}")
        
        logger.info(f"\n--- Technology ---")
        logger.info(f"CRM: {result.crm}")
        logger.info(f"Cloud: {result.cloud_provider}")
        if result.other_tools:
            logger.info(f"Tools: {', '.join(result.other_tools)}")
        
        logger.info(f"\n--- Competitive ---")
        logger.info(f"Position: {result.market_position}")
        if result.main_competitors:
            logger.info(f"Competitors: {', '.join(result.main_competitors)}")
        if result.differentiators:
            logger.info(f"Differentiators:")
            for diff in result.differentiators:
                logger.info(f"  - {diff}")
        
        # Output markdown for Claude
        logger.info(f"\n{'='*60}")
        logger.info("CLAUDE-READY MARKDOWN OUTPUT")
        logger.info(f"{'='*60}\n")
        markdown = service.format_for_claude(result)
        print(markdown)
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown)
            logger.info(f"\nSaved to: {output_file}")
            
            # Also save raw JSON
            json_file = output_file.replace('.md', '.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result.raw_output, f, indent=2)
            logger.info(f"Raw JSON saved to: {json_file}")
        
    else:
        logger.error(f"❌ FAILED after {elapsed:.1f}s")
        for error in result.errors:
            logger.error(f"  Error: {error}")


def main():
    parser = argparse.ArgumentParser(description='Test Exa Research for a single company')
    parser.add_argument('company_name', help='Name of the company to research')
    parser.add_argument('--country', '-c', help='Country for regional context')
    parser.add_argument('--linkedin', '-l', help='LinkedIn company URL')
    parser.add_argument('--website', '-w', help='Company website URL')
    parser.add_argument('--model', '-m', default='exa-research',
                       choices=['exa-research', 'exa-research-pro'],
                       help='Exa model to use (default: exa-research)')
    parser.add_argument('--output', '-o', help='Output file for markdown result')
    
    args = parser.parse_args()
    
    asyncio.run(test_company(
        company_name=args.company_name,
        country=args.country,
        linkedin_url=args.linkedin,
        website_url=args.website,
        model=args.model,
        output_file=args.output
    ))


if __name__ == "__main__":
    main()
