# DealMotion Web

AI-powered sales enablement platform - Put your deals in motion.

## Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, Python 3.11, Inngest
- **Database**: PostgreSQL (Supabase)
- **Auth**: Supabase Auth
- **Payments**: Stripe

## Project Structure

```
dealmotion-web/
├── frontend/          # Next.js frontend
│   ├── app/           # App router pages
│   ├── components/    # React components
│   ├── hooks/         # Custom hooks
│   ├── lib/           # Utilities
│   └── messages/      # i18n translations
│
└── backend/           # FastAPI backend
    ├── app/
    │   ├── routers/   # API endpoints
    │   ├── services/  # Business logic
    │   ├── models/    # Pydantic models
    │   └── inngest/   # Workflow functions
    └── database/      # SQL migrations
```

## Deployment

- **Frontend**: Vercel (auto-deploy from `main`)
- **Backend**: Railway (auto-deploy from `main`)

## Environment Variables

See `frontend/.env.example` and `backend/env.example` for required variables.

## Development

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Links

- **Production**: https://dealmotion.ai
- **API**: https://api.dealmotion.ai

