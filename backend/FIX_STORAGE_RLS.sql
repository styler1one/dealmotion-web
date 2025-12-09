-- Fix Storage RLS Policies for knowledge-base-files bucket
-- Run this in Supabase SQL Editor

-- First, drop all existing policies on storage.objects for our bucket
DROP POLICY IF EXISTS "Users can upload to their org folder" ON storage.objects;
DROP POLICY IF EXISTS "Users can read their org files" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their org files" ON storage.objects;
DROP POLICY IF EXISTS "Allow authenticated uploads" ON storage.objects;
DROP POLICY IF EXISTS "Allow authenticated reads" ON storage.objects;
DROP POLICY IF EXISTS "Allow authenticated deletes" ON storage.objects;

-- Create new policies that work with service role key
-- Service role key should bypass RLS, but we add these for safety

-- Allow service role to do everything (this should work by default but let's be explicit)
CREATE POLICY "Service role full access"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'knowledge-base-files')
WITH CHECK (bucket_id = 'knowledge-base-files');

-- Allow authenticated users to upload to any folder
-- (We check permissions in backend code before upload)
CREATE POLICY "Authenticated users can upload"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'knowledge-base-files');

-- Allow authenticated users to read any file
-- (We check permissions in backend code before returning file list)
CREATE POLICY "Authenticated users can read"
ON storage.objects
FOR SELECT
TO authenticated
USING (bucket_id = 'knowledge-base-files');

-- Allow authenticated users to delete any file
-- (We check permissions in backend code before delete)
CREATE POLICY "Authenticated users can delete"
ON storage.objects
FOR DELETE
TO authenticated
USING (bucket_id = 'knowledge-base-files');

-- Verify policies
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE tablename = 'objects' 
AND schemaname = 'storage'
ORDER BY policyname;
