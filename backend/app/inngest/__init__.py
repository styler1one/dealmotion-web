"""
Inngest Workflow Orchestration for DealMotion.

This module provides event-driven workflow orchestration using Inngest,
enabling durable execution, automatic retries, and full observability
for all AI-powered workflows.

Usage:
    from app.inngest import inngest_client, functions
    
    # In main.py:
    serve(app, inngest_client, functions)
"""

from .client import inngest_client
from .functions import all_functions

# Export for easy import
__all__ = ["inngest_client", "all_functions"]

