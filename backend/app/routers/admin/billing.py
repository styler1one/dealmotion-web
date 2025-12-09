"""
Admin Billing Router
====================

Endpoints for billing overview and transaction management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os

from app.deps import get_admin_user, require_admin_role, AdminContext
from app.database import get_supabase_service
from .models import CamelModel

router = APIRouter(prefix="/billing", tags=["admin-billing"])


# ============================================================
# Models (with camelCase serialization)
# ============================================================

class BillingOverview(CamelModel):
    mrr_cents: int
    mrr_formatted: str
    arr_cents: int
    arr_formatted: str
    paid_users: int
    free_users: int
    trial_users: int
    churn_rate_30d: float
    plan_distribution: Dict[str, int]


class TransactionItem(CamelModel):
    id: str
    organization_id: str
    organization_name: Optional[str] = None
    amount_cents: int
    amount_formatted: str
    type: str  # 'subscription', 'flow_pack', 'refund'
    status: str
    created_at: datetime


class TransactionListResponse(CamelModel):
    transactions: List[TransactionItem]
    total: int


class FailedPaymentItem(CamelModel):
    id: str
    customer_email: str
    organization_name: Optional[str] = None
    amount_cents: int
    amount_formatted: str
    attempt_count: int
    next_attempt: Optional[datetime] = None
    created_at: datetime


class FailedPaymentsResponse(CamelModel):
    failed_payments: List[FailedPaymentItem]
    total: int


# ============================================================
# Endpoints
# ============================================================

@router.get("/overview", response_model=BillingOverview)
async def get_billing_overview(
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Get billing overview metrics.
    
    Returns:
    - MRR (Monthly Recurring Revenue)
    - ARR (Annual Recurring Revenue)
    - User counts by type
    - Churn rate (30 days)
    - Plan distribution
    """
    supabase = get_supabase_service()
    
    # Get MRR from database function
    mrr_cents = 0
    paid_users = 0
    
    try:
        mrr_result = supabase.rpc("calculate_mrr").execute()
        if mrr_result.data:
            mrr_data = mrr_result.data
            mrr_cents = mrr_data.get("mrr_cents", 0) or 0
            paid_users = mrr_data.get("paid_users", 0) or 0
    except Exception:
        pass
    
    # Fallback: calculate MRR manually if RPC failed or returned 0
    if mrr_cents == 0:
        try:
            # Get active subscriptions with their plan prices
            subs_result = supabase.table("organization_subscriptions") \
                .select("plan_id, subscription_plans(price_monthly_cents)") \
                .eq("status", "active") \
                .execute()
            
            for sub in (subs_result.data or []):
                if sub.get("subscription_plans"):
                    price = sub["subscription_plans"].get("price_monthly_cents", 0) or 0
                    if price > 0:
                        mrr_cents += price
                        paid_users += 1
        except Exception:
            pass
    
    # Get user counts
    total_users = supabase.table("users").select("id", count="exact").execute()
    free_users = (total_users.count or 0) - paid_users
    
    # Get trial users
    trial_result = supabase.table("organization_subscriptions") \
        .select("id", count="exact") \
        .eq("status", "trialing") \
        .execute()
    trial_users = trial_result.count or 0
    
    # Get plan distribution
    plan_result = supabase.table("organization_subscriptions") \
        .select("plan_id") \
        .eq("status", "active") \
        .execute()
    
    plan_distribution = {}
    for sub in (plan_result.data or []):
        plan = sub.get("plan_id", "unknown")
        plan_distribution[plan] = plan_distribution.get(plan, 0) + 1
    
    # Calculate churn rate (simplified: cancellations / total in last 30 days)
    cancelled_result = supabase.table("organization_subscriptions") \
        .select("id", count="exact") \
        .eq("status", "cancelled") \
        .gte("updated_at", (datetime.utcnow() - timedelta(days=30)).isoformat()) \
        .execute()
    
    cancelled = cancelled_result.count or 0
    churn_rate = (cancelled / paid_users * 100) if paid_users > 0 else 0.0
    
    return BillingOverview(
        mrr_cents=mrr_cents,
        mrr_formatted=f"€{mrr_cents / 100:.2f}",
        arr_cents=mrr_cents * 12,
        arr_formatted=f"€{mrr_cents * 12 / 100:.2f}",
        paid_users=paid_users,
        free_users=free_users,
        trial_users=trial_users,
        churn_rate_30d=round(churn_rate, 2),
        plan_distribution=plan_distribution
    )


@router.get("/transactions", response_model=TransactionListResponse)
async def get_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Get recent transactions.
    
    Query params:
    - status: 'paid', 'failed', 'refunded', 'pending'
    """
    supabase = get_supabase_service()
    
    query = supabase.table("payment_history") \
        .select("*, organizations(name)", count="exact")
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    result = query \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()
    
    transactions = []
    for t in (result.data or []):
        org_name = t["organizations"]["name"] if t.get("organizations") else None
        
        # Determine transaction type from status
        status = t.get("status", "unknown")
        tx_type = "refund" if status == "refunded" else "subscription"
        
        transactions.append(TransactionItem(
            id=t["id"],
            organization_id=t["organization_id"],
            organization_name=org_name,
            amount_cents=t.get("amount_cents", 0),
            amount_formatted=f"€{t.get('amount_cents', 0) / 100:.2f}",
            type=tx_type,
            status=status,
            created_at=t["created_at"]
        ))
    
    return TransactionListResponse(
        transactions=transactions,
        total=result.count or len(transactions)
    )


@router.get("/failed-payments", response_model=FailedPaymentsResponse)
async def get_failed_payments(
    admin: AdminContext = Depends(require_admin_role("super_admin", "admin"))
):
    """
    Get failed payments requiring action.
    
    This fetches data from Stripe API for real-time accuracy.
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        return FailedPaymentsResponse(failed_payments=[], total=0)
    
    try:
        import stripe
        stripe.api_key = stripe_key
        
        # Get open invoices with payment attempts
        invoices = stripe.Invoice.list(
            status="open",
            limit=50,
            expand=["data.customer"]
        )
        
        failed_payments = []
        supabase = get_supabase_service()
        
        for inv in invoices.data:
            if inv.attempt_count > 0:  # Has failed at least once
                # Try to find organization
                org_name = None
                if inv.customer:
                    org_result = supabase.table("organization_subscriptions") \
                        .select("organizations(name)") \
                        .eq("stripe_customer_id", inv.customer.id) \
                        .maybe_single() \
                        .execute()
                    
                    if org_result.data and org_result.data.get("organizations"):
                        org_name = org_result.data["organizations"]["name"]
                
                failed_payments.append(FailedPaymentItem(
                    id=inv.id,
                    customer_email=inv.customer.email if inv.customer else "Unknown",
                    organization_name=org_name,
                    amount_cents=inv.amount_due,
                    amount_formatted=f"€{inv.amount_due / 100:.2f}",
                    attempt_count=inv.attempt_count,
                    next_attempt=datetime.fromtimestamp(inv.next_payment_attempt) if inv.next_payment_attempt else None,
                    created_at=datetime.fromtimestamp(inv.created)
                ))
        
        return FailedPaymentsResponse(
            failed_payments=failed_payments,
            total=len(failed_payments)
        )
    
    except Exception as e:
        print(f"Error fetching failed payments from Stripe: {e}")
        return FailedPaymentsResponse(failed_payments=[], total=0)

