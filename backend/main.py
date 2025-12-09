from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import users, knowledge_base, research, sales_profile, company_profile, context, preparation, followup, followup_actions, prospects, contacts, settings, billing, webhooks, deals, coach, dashboard, calendar, calendar_meetings, integrations, recordings

# Import mobile router separately to catch potential errors
try:
    from app.routers import mobile
    MOBILE_ROUTER_AVAILABLE = True
except Exception as e:
    logging.error(f"Failed to import mobile router: {e}")
    MOBILE_ROUTER_AVAILABLE = False
from app.routers.admin import router as admin_router

# Sentry imports (error tracking)
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            # Set traces_sample_rate to 1.0 to capture 100% of transactions for tracing.
            # We recommend adjusting this in production.
            traces_sample_rate=0.1,
            # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
            # We recommend adjusting this in production.
            profiles_sample_rate=0.1,
            # Enable performance monitoring
            enable_tracing=True,
            # Environment tag
            environment=os.getenv("ENVIRONMENT", "development"),
            # Release version
            release=os.getenv("RELEASE_VERSION", "1.12.0"),
            # Integrations
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
            ],
            # Filter out health checks
            before_send=lambda event, hint: None if event.get("request", {}).get("url", "").endswith("/health") else event,
        )
        SENTRY_ENABLED = True
        logging.info("Sentry error tracking enabled")
    else:
        SENTRY_ENABLED = False
        logging.info("Sentry DSN not configured, error tracking disabled")
except ImportError:
    SENTRY_ENABLED = False
    logging.warning("Sentry SDK not installed, error tracking disabled")

# Inngest imports (workflow orchestration)
try:
    import inngest.fast_api
    from app.inngest import inngest_client, all_functions
    INNGEST_ENABLED = True
except ImportError:
    INNGEST_ENABLED = False
    logging.warning("Inngest not installed, workflow orchestration disabled")

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter configuration
# Uses remote address for identification
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="DealMotion API",
    description="AI-powered sales enablement - Put your deals in motion",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter

# Custom rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded for {get_remote_address(request)}")
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail
        }
    )

# CORS configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(knowledge_base.router, prefix="/api/v1/knowledge-base", tags=["knowledge-base"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(sales_profile.router)  # Already has prefix
app.include_router(company_profile.router)  # Already has prefix
app.include_router(context.router)  # Already has prefix
app.include_router(preparation.router, prefix="/api/v1/prep", tags=["preparation"])
app.include_router(followup.router, prefix="/api/v1", tags=["followup"])
app.include_router(followup_actions.router, prefix="/api/v1", tags=["followup-actions"])
app.include_router(prospects.router, prefix="/api/v1", tags=["prospects"])
app.include_router(contacts.router, prefix="/api/v1", tags=["contacts"])
app.include_router(settings.router)  # Already has prefix
app.include_router(billing.router, prefix="/api/v1", tags=["billing"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
app.include_router(deals.router)  # Already has prefix /api/v1/deals
app.include_router(deals.meetings_router)  # Already has prefix /api/v1/meetings
app.include_router(deals.hub_router)  # Already has prefix /api/v1/prospects (extends existing)
app.include_router(coach.router)  # Already has prefix /api/v1/coach
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(calendar.router)  # Already has prefix /api/v1/calendar
app.include_router(calendar_meetings.router)  # Already has prefix /api/v1/calendar-meetings
app.include_router(integrations.router)  # Already has prefix /api/v1/integrations
app.include_router(recordings.router)  # Already has prefix /api/v1/recordings

# Mobile router (conditionally included)
if MOBILE_ROUTER_AVAILABLE:
    app.include_router(mobile.router, prefix="/api/v1/mobile", tags=["mobile"])
else:
    logger.warning("Mobile router not available, mobile endpoints will not work")

# Admin panel routes (protected by admin role check)
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])

# Inngest webhook endpoint for workflow orchestration
if INNGEST_ENABLED:
    inngest.fast_api.serve(
        app,
        inngest_client,
        all_functions,
    )
    logger.info("Inngest workflow orchestration enabled at /api/inngest")

@app.get("/")
def read_root():
    return {
        "message": "Welcome to DealMotion API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "sentry": "enabled" if SENTRY_ENABLED else "disabled",
        "inngest": "enabled" if INNGEST_ENABLED else "disabled"
    }

@app.get("/api/v1/test")
def test_endpoint():
    """Test endpoint to verify backend is working"""
    return {
        "message": "Backend is working!",
        "database": "connected" if os.getenv("DATABASE_URL") else "not configured",
        "supabase": "configured" if os.getenv("SUPABASE_URL") else "not configured"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
