# Supabase Setup Guide for Tax Intelligence Platform

## Overview

This guide will help you set up Supabase to work with your Tax Intelligence Platform RAG pipeline.

## Prerequisites

- Supabase account (you already have the project at `https://hiylvfwlwclpdediijgx.supabase.co`)
- The API key is already configured in your `.env` file

## Step 1: Enable pgvector Extension

1. Go to your Supabase dashboard
2. Navigate to **Settings** → **Database**
3. Click **Database Dev** tab
4. Go to **Extensions**
5. Enable `vector` extension
6. Note: pgvector is pre-installed on all Supabase instances

## Step 2: Create Database Schema

1. In your Supabase dashboard, go to **Tools** → **SQL Editor**
2. Copy and paste the SQL below and execute it:

```sql
-- Enable the pgvector extension (should already be enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the main table for tax documents
CREATE TABLE IF NOT EXISTS tax_documents (
    id BIGSERIAL PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL,
    document_type TEXT,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),  -- OpenAI ada-002 embeddings
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for optimal performance
CREATE INDEX IF NOT EXISTS tax_docs_content_idx ON tax_documents USING gin(to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS tax_docs_type_idx ON tax_documents(document_type);
CREATE INDEX IF NOT EXISTS tax_docs_metadata_idx ON tax_documents USING gin(metadata);
CREATE INDEX IF NOT EXISTS tax_docs_created_at_idx ON tax_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS tax_docs_embedding_idx ON tax_documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

-- Function for vector similarity search
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.6,
    match_count int DEFAULT 10
)
RETURNS TABLE(
    id bigint,
    title text,
    content text,
    document_type text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        tax_documents.id,
        tax_documents.title,
        tax_documents.content,
        tax_documents.document_type,
        tax_documents.metadata,
        1 - (tax_documents.embedding <=> query_embedding) AS similarity
    FROM tax_documents
    WHERE 1 - (tax_documents.embedding <=> query_embedding) > match_threshold
    ORDER BY tax_documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Insert some test data
INSERT INTO tax_documents (title, content, document_type, metadata) VALUES
(
    'Section 338(h)(10) Election Requirements',
    'Section 338(h)(10) provides a mechanism for partners in a partnership to step up the basis of their partnership interest without triggering immediate tax recognition. The election allows partners to recognize gain on the excess of the FMV over their basis in the partnership interest. Requirements for making the election include: 1. The partnership must have at least 10 partners 2. All partners must consent to the election 3. The election must be made on or before the 15th day of the 4th month after the end of the tax year 4. The partnership must file the election with Form 8023.',
    'regulation',
    '{"section": "338(h)(10)", "topic": "partnership basis step-up", "year": 2024, "authority": "irc_tax_code"}'::jsonb
),
(
    'Case Law: Smith v. Commissioner - Basis Step Up',
    'In Smith v. Commissioner, the Tax Court held that the taxpayer could not step up the basis of partnership interests under Section 338(h)(10). The court reasoned that the partnership did not meet the qualified bankruptcy exception requirements. The court determined that even though the partnership was in bankruptcy, the taxpayer was not a qualified purchaser because they were not buying substantially all the assets.',
    'case_law',
    '{"case": "Smith v. Commissioner", "year": "2018", "court": "tax_court", "section": "338(h)(10)"}'::jsonb
),
(
    'Internal Revenue Code Section 754 Election',
    'Section 754 allows partners to adjust their basis in partnership property after certain partnership distributions. This election can be made unilaterally by any partner and results in a deemed sale of assets within the partnership, allowing partners to receive basis adjustments without triggering taxable gain.',
    'regulation',
    '{"section": "754", "topic": "basis adjustment", "year": 2024}'::jsonb
);
```

## Step 3: Verify Setup

### Check Table Created

```sql
SELECT table_name FROM information_schema.tables
WHERE table_catalog = 'postgres' AND table_schema = 'public'
AND table_name = 'tax_documents';
```

### Check Extension Enabled

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Verify Data Exists

```sql
SELECT COUNT(*) as total_documents FROM tax_documents;
SELECT document_type, COUNT(*) FROM tax_documents GROUP BY document_type;
```

## Step 4: Test Connection

Your code should now be able to:

1. ✅ Connect to Supabase
2. ✅ Generate embeddings using OpenAI
3. ✅ Store documents with embeddings
4. ✅ Perform vector similarity search
5. ✅ Return results

## Troubleshooting

### If getting 404 errors:

- Verify the table `tax_documents` exists in your Supabase project
- Check that you have the right permissions
- The API key should have read/write access

### If getting empty results:

- Make sure you have documents in the table
- Check if the embeddings were generated properly
- Verify the document data structure matches expected format

### Performance Optimization:

- The IVF-flat index improves query speed
- Adjust the similarity threshold in queries as needed
- Consider batch insertions for large datasets

## Next Steps

1. **Test the API**: Run your RAG pipeline and verify documents are found
2. **Populate Data**: Use the bulk insertion methods to add more tax documents
3. **Monitor Usage**: Check Supabase dashboard for query performance and costs

Your Supabase setup is now complete! 🚀
