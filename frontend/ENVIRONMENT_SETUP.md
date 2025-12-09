# Frontend Environment Setup

## Required Environment Variables

Create a `.env.local` file in the `frontend` directory with the following variables:

```bash
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url_here
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Backend API URL
NEXT_PUBLIC_API_URL=https://api.dealmotion.ai
```

## Getting Your Supabase Credentials

1. Go to your Supabase project dashboard
2. Click on "Settings" → "API"
3. Copy the "Project URL" → use as `NEXT_PUBLIC_SUPABASE_URL`
4. Copy the "anon public" key → use as `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Development

```bash
npm run dev
```

## Production

```bash
npm run build
npm start
```
