# Railway Environment Variables

## Required Environment Variables

Add these to your Railway deployment:

### Supabase Configuration

1. **SUPABASE_URL**
   - Your Supabase project URL
   - Example: `https://xxxxx.supabase.co`

2. **SUPABASE_KEY**
   - Your Supabase **ANON** key (public key)
   - Found in: Supabase Dashboard → Settings → API → Project API keys → `anon` `public`
   - Used for: User-facing operations with RLS

3. **SUPABASE_SERVICE_ROLE_KEY** ⚠️ **REQUIRED**
   - Your Supabase **SERVICE ROLE** key (secret key)
   - Found in: Supabase Dashboard → Settings → API → Project API keys → `service_role` (click to reveal)
   - Used for: Background tasks, storage operations, admin operations
   - **WARNING:** This key bypasses RLS - keep it secret!

4. **SUPABASE_JWT_SECRET**
   - Your Supabase JWT secret
   - Found in: Supabase Dashboard → Settings → API → JWT Settings → JWT Secret
   - Used for: Verifying JWT tokens

### Other Configuration

5. **ALLOWED_ORIGINS**
   - Comma-separated list of allowed CORS origins
   - Example: `https://sdx.agentboss.nl,http://localhost:3000`

6. **VOYAGE_API_KEY**
   - Your Voyage AI API key for embeddings
   - Get from: https://www.voyageai.com/

7. **PINECONE_API_KEY**
   - Your Pinecone API key for vector storage
   - Get from: https://www.pinecone.io/

8. **PINECONE_ENVIRONMENT**
   - Your Pinecone environment
   - Example: `us-east-1-aws`

9. **PINECONE_INDEX_NAME**
   - Your Pinecone index name
   - Example: `dealmotion-knowledge-base`

## How to Add in Railway

1. Go to your Railway project
2. Click on your service
3. Go to "Variables" tab
4. Click "New Variable"
5. Add each variable with its value
6. Railway will automatically redeploy

## Security Notes

- ✅ **SUPABASE_KEY** (anon): Safe to expose to frontend
- ⚠️ **SUPABASE_SERVICE_ROLE_KEY**: NEVER expose to frontend - backend only!
- ⚠️ **SUPABASE_JWT_SECRET**: Keep secret - backend only!
- ⚠️ **API Keys**: All API keys should be kept secret

## Verification

After adding all variables, check Railway logs for:
- No "missing environment variable" errors
- Successful Supabase connections
- No RLS policy violations on storage operations
