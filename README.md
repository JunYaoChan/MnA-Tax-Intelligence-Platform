# M&A Tax Intelligence Platform

AI-powered tax research and analysis for complex M&A transactions. This project combines a Next.js frontend with a FastAPI backend, a Supabase pgvector document store for semantic retrieval, and a Neo4j graph for entity relationships. It supports secure Auth0 authentication, live streaming chat responses, interactive markdown rendering, and multiple synthesis strategies depending on query complexity.

## Table of Contents

- Overview
- Key Features
- Architecture
- Tech Stack
- Prerequisites
- Setup
  - 1. Frontend (Next.js + Auth0)
  - 2. Backend (FastAPI)
  - 3. Datastores
    - Supabase + pgvector
    - Neo4j Graph
- Run Locally
- Usage Guide
- Synthesis Strategies
- Troubleshooting
- Testing
- License

---

## Overview

The platform ingests tax-related documents (regulations, case law, revenue rulings, internal notes, etc.), chunks and embeds them into a pgvector-enabled Supabase table, optionally extracts entities into Neo4j, and leverages an orchestrated multi-agent RAG pipeline to retrieve, analyze, and synthesize answers. Responses stream back to the UI in real-time with interactive markdown rendering, including syntax highlighting, copyable code blocks, and linkable headings.

## Key Features

- Secure login with Auth0
- Document upload (file and text), chunking, embedding, and storage
- Vector search (RPC or REST fallback) with optional hybrid retrieval
- Optional Neo4j graph entity extraction and linking
- Multi-agent orchestrator (Regulation, Case Law, Precedent, Expert, Query Planning)
- LLM-based synthesis with strategy selection (simple, moderate, complex, expert)
- Live SSE streaming to the chat interface
- Interactive markdown rendering in the UI (GFM, tables, code highlighting, copy buttons)

## Architecture

- Frontend (Next.js 15, React 19)
  - Auth0 authentication
  - Chat UI with streaming SSE
  - Interactive markdown with GitHub-flavored Markdown and syntax highlighting
- Backend (FastAPI)
  - REST API for chat and uploads
  - RAG orchestrator and agent pipeline
  - Supabase vector store client (pgvector)
  - Neo4j graph client
- Datastores
  - Supabase Postgres with pgvector for embeddings
  - Neo4j for entities and relationships

## Tech Stack

- Frontend: Next.js, React, react-markdown, remark-gfm, rehype-highlight, Reactstrap
- Auth: Auth0 Next.js SDK
- Backend: FastAPI (Uvicorn), Python 3.11
- Data: Supabase (Postgres + pgvector), Neo4j
- LLM: OpenAI for embeddings and synthesis
- Search: Brave Search (optional function tool)

## Prerequisites

- Node.js 18+ (Node 22 is fine) and npm
- Python 3.11+
- A Supabase project (URL + service role key)
- A Neo4j instance (local or remote)
- OpenAI API key
- (Optional) Brave Search API key for external web search

---

## Setup

### 1) Frontend (Next.js + Auth0)

Install dependencies:

```bash
npm install
```

Create `./.env.local` from your Auth0 application:

```bash
# Required Auth0 config
AUTH0_SECRET='LONG_RANDOM_VALUE'          # openssl rand -hex 32
APP_BASE_URL='http://localhost:3000'
AUTH0_DOMAIN='YOUR_TENANT.auth0.com'
AUTH0_CLIENT_ID='YOUR_AUTH0_CLIENT_ID'
AUTH0_CLIENT_SECRET='YOUR_AUTH0_CLIENT_SECRET'

# Optional Auth0 API (only if you want to call a protected API)
# AUTH0_AUDIENCE='YOUR_AUTH0_API_IDENTIFIER'
# AUTH0_SCOPE='openid profile email read:shows'
```

Notes:

- The dev script also starts a sample Node API server on port 3001 (used by the Auth0 sample pages). It’s independent from the FastAPI backend.

### 2) Backend (FastAPI)

The backend lives under `./Backend`.

Create a Python virtual environment and install:

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt || pip install "uvicorn[standard]" "python-dotenv" "httpx" "pydantic" "neo4j" "supabase" "openai" # fallback if no requirements.txt
```

Create `./Backend/.env` with:

```bash
# Supabase
SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY="YOUR_SERVICE_ROLE_KEY"

# Neo4j
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your_password"

# APIs / LLM
OPENAI_API_KEY="sk-..."
BRAVE_SEARCH_API_KEY=""  # optional

# RAG settings (defaults shown)
LLM_MODEL="gpt-4"
EMBEDDING_MODEL="text-embedding-ada-002"
TOP_K_RESULTS="10"
VECTOR_SIMILARITY_THRESHOLD="0.7"
ENABLE_HYBRID_SEARCH="false"

# Disable broken RPC until you update the function in Supabase (see below)
USE_SUPABASE_RPC="false"
```

### 3) Datastores

#### Supabase + pgvector

Enable pgvector and create the documents table (run in Supabase SQL editor). The backend provides a helper SQL via `SupabaseVectorStore.initialize_database()`; here’s the canonical version without the removed `document_type` column:

```sql
-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the table for tax documents
CREATE TABLE IF NOT EXISTS tax_documents (
  id BIGSERIAL PRIMARY KEY,
  title TEXT,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  embedding vector(1536),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS tax_docs_content_idx ON tax_documents USING gin(to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS tax_docs_metadata_idx ON tax_documents USING gin(metadata);
CREATE INDEX IF NOT EXISTS tax_docs_created_at_idx ON tax_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS tax_docs_embedding_idx ON tax_documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

-- Vector similarity search function WITHOUT document_type (important)
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10
)
RETURNS TABLE(
  id bigint,
  title text,
  content text,
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
    tax_documents.metadata,
    1 - (tax_documents.embedding <=> query_embedding) AS similarity
  FROM tax_documents
  WHERE 1 - (tax_documents.embedding <=> query_embedding) > match_threshold
  ORDER BY tax_documents.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

Chat/browsing metadata tables:

- See `Backend/setup_supabase_chat.sql` for creating `documents`, `conversations`, and `conversation_documents` used by the chat repository. Execute that SQL in Supabase as well.

Important: This project no longer uses a `document_type` column in Supabase; types are stored under `metadata.document_type`. If you previously had indexes on `document_type`, drop them, and re-run the function above.

#### Neo4j Graph

- Start Neo4j locally or connect to a remote instance.
- Put your URI, user, password into `Backend/.env`.
- On upload, the backend can extract entities (e.g. sections, cases) and create nodes/relationships for cross-references.

---

## Run Locally

Start Backend (FastAPI):

```bash
cd Backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Start Frontend (Next.js) in a separate terminal:

```bash
npm run dev
```

- Frontend: http://localhost:3000
- FastAPI Backend (used by the UI): http://localhost:8000
- The dev script also starts a sample Node API server on port 3001; you can ignore it for core functionality.

---

## Usage Guide

1. Sign in with Auth0 from the landing page.
2. Create or select a conversation in the left sidebar.
3. Upload documents (PDF/DOCX/TXT) or paste text:
   - Files are chunked, embedded via OpenAI, and stored in Supabase
   - Optional entities are extracted and persisted into Neo4j
4. Ask questions in the chat input:
   - The orchestrator refines the query, retrieves relevant documents, and synthesizes an answer
   - The answer streams live and is rendered as interactive markdown (GFM, tables, syntax highlighting, copyable code)
   - The synthesis strategy used appears in the debug panel and at the end of the answer as `[Strategy: ...]`

Tips:

- Put high-level tags like `document_type` under `metadata.document_type` when inserting documents.
- Use the conversation document controls to unlink or remove records.

---

## Synthesis Strategies

The backend selects a synthesis strategy based on `QueryComplexity`:

- `simple`: Concise summary, key findings, recommendations
- `moderate`: Executive summary, detailed findings by source, conflict analysis
- `complex`: Multi-stage analysis composed and synthesized into an executive-ready response
- `expert`: Function-call schema to produce a structured expert analysis
- `fallback`: Minimal, used when the LLM is unavailable

The UI logs the strategy in the debug panel and appends `[Strategy: ...]` to the final message.

---

## Troubleshooting

- RPC error “column tax_documents.document_type does not exist”:

  - The project removed the `document_type` column. Update the `match_documents` function to the version in this README, and ensure any old `document_type` indexes are dropped.
  - In the backend `.env`, keep `USE_SUPABASE_RPC=false` until you update the Supabase function; the code will use a REST fallback and derive `document_type` from `metadata`.

- Build errors with Babel unicode regex / remark-gfm / highlight.js:

  - We removed `.babelrc` to use SWC (Next’s default), which resolves those issues. If you reintroduce custom Babel config, you may see unicode property errors again.

- Port already in use (3001) when running `npm run dev`:
  - The sample API server (node) uses 3001. Stop any process occupying that port or modify the scripts if you don’t need the sample API server.

---

## Testing

- Unit tests:

```bash
npm run test
```

- Integration tests (Cypress):

```bash
npm run test:integration
```

---

## License

This project is licensed under the MIT license. See the [LICENSE](./LICENSE) file for more info.
