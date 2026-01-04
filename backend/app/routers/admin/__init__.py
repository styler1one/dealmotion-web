"""
Admin Panel Routers
===================

This module contains all admin panel endpoints for DealMotion.
All routes are protected and require admin role verification.

Routers:
- dashboard: Dashboard metrics and trends
- users: User management and details
- notes: Admin notes on users/organizations
- alerts: System alert management
- health: System health monitoring (services, uptime, trends)
- costs: API cost tracking and analytics
- billing: Billing overview and transactions
- audit: Audit log viewing
- affiliates: Affiliate program management
- luna: Luna shadow mode monitoring (SPEC-046)

Access Levels:
- super_admin: Full access, can manage other admins
- admin: Full access except admin management
- support: User viewing, basic actions, notes
- viewer: Read-only access
"""

from fastapi import APIRouter

# Import sub-routers
from .dashboard import router as dashboard_router
from .users import router as users_router
from .notes import router as notes_router
from .alerts import router as alerts_router
from .health import router as health_router
from .costs import router as costs_router
from .billing import router as billing_router
from .audit import router as audit_router
from .affiliates import router as affiliates_router
from .luna import router as luna_router

# Create main admin router
router = APIRouter(prefix="/admin", tags=["admin"])

# Include all sub-routers
router.include_router(dashboard_router)
router.include_router(users_router)
router.include_router(notes_router)
router.include_router(alerts_router)
router.include_router(health_router)
router.include_router(costs_router)
router.include_router(billing_router)
router.include_router(audit_router)
router.include_router(affiliates_router)
router.include_router(luna_router)

__all__ = ["router"]

