# Research Agent Environment Variables

## Required Environment Variables

Add these to your Railway deployment for the Research Agent feature:

### AI APIs

1. **ANTHROPIC_API_KEY** ✅ (Already configured from Knowledge Base)
   - Your Anthropic Claude API key
   - Used for: Claude web search and research brief generation
   - Get from: https://console.anthropic.com/

2. **GOOGLE_AI_API_KEY** 🆕 (NEW - FREE!)
   - Your Google AI (Gemini) API key
   - Used for: Gemini Google Search integration
   - Get from: https://makersuite.google.com/app/apikey
   - **FREE tier**: 15 requests/minute
   - **How to get**:
     1. Go to Google AI Studio
     2. Click "Get API Key"
     3. Create new API key
     4. Copy and add to Railway

### Data APIs

3. **KVK_API_KEY** 🆕 (NEW - FREE!)
   - Your KVK (Kamer van Koophandel) API key
   - Used for: Official Dutch company data
   - Get from: https://developers.kvk.nl/
   - **FREE tier**: Available for basic usage
   - **How to get**:
     1. Register at KVK Developer Portal
     2. Create an application
     3. Get API key
     4. Copy and add to Railway
   - **Optional**: Only needed for Dutch companies

### Storage (Already configured)

4. **SUPABASE_STORAGE_BUCKET** ✅
   - Bucket name: `research-pdfs`
   - Already created in database schema

## How to Add in Railway

1. Go to your Railway project
2. Click on your backend service
3. Go to "Variables" tab
4. Click "New Variable"
5. Add each new variable:
   ```
   GOOGLE_AI_API_KEY=your_gemini_api_key_here
   KVK_API_KEY=your_kvk_api_key_here (optional)
   ```
6. Railway will automatically redeploy

## Verification

After adding variables, check Railway logs for:
- No "environment variable not set" errors
- Successful API connections
- Research requests working

## Cost Breakdown

| Service | Cost | Usage Limit |
|---------|------|-------------|
| Claude API | ~$5/month | Already have |
| Gemini API | **FREE** | 15 req/min |
| KVK API | **FREE** | Basic tier |
| **Total** | **$5/month** | 🎉 |

## Notes

- ✅ **GOOGLE_AI_API_KEY**: FREE tier is generous for MVP
- ✅ **KVK_API_KEY**: Optional, only for Dutch companies
- ⚠️ **Keep all API keys secret** - never commit to git
- 🔒 **Railway encrypts** all environment variables

## Testing

After deployment, test with:
```bash
curl -X POST https://your-backend.railway.app/api/v1/research/start \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Company",
    "country": "Netherlands",
    "city": "Amsterdam"
  }'
```

Expected response:
```json
{
  "id": "uuid",
  "company_name": "Test Company",
  "status": "pending",
  "created_at": "2025-11-26T..."
}
```
