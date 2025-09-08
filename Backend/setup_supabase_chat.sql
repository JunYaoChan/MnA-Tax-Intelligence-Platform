-- Supabase schema for chat persistence and document linkage
-- Run this in Supabase SQL editor

-- Enable extensions (uuid + time helpers)
create extension if not exists pgcrypto;

-- Users table (optional; can store app-specific profiles)
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  auth0_id text unique,
  email text,
  name text,
  preferences jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- Conversations
create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,  -- store auth0 sub (e.g., 'auth0|abc123')
  title text,
  created_at timestamp with time zone default now()
);

create index if not exists idx_conversations_user_id on conversations(user_id);
create index if not exists idx_conversations_created_at on conversations(created_at desc);

-- Messages
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  role text not null check (role in ('user','assistant','system')),
  content text not null,
  created_at timestamp with time zone default now(),
  foreign key (conversation_id) references conversations(id) on delete cascade
);

create index if not exists idx_messages_conversation_id on messages(conversation_id);
create index if not exists idx_messages_created_at on messages(created_at);

-- High-level uploaded documents (metadata; content chunks go to tax_documents via pgvector)
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  filename text not null,
  document_type text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

create index if not exists idx_documents_user_id on documents(user_id);
create index if not exists idx_documents_created_at on documents(created_at desc);

-- Conversation ↔ Document linking
create table if not exists conversation_documents (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  document_id uuid not null,
  created_at timestamp with time zone default now(),
  foreign key (conversation_id) references conversations(id) on delete cascade,
  foreign key (document_id) references documents(id) on delete cascade,
  unique (conversation_id, document_id)
);

create index if not exists idx_conversation_documents_conversation_id on conversation_documents(conversation_id);
create index if not exists idx_conversation_documents_document_id on conversation_documents(document_id);

-- Optional RLS policies (adjust as needed)
-- alter table conversations enable row level security;
-- alter table messages enable row level security;
-- alter table documents enable row level security;
-- alter table conversation_documents enable row level security;

-- Example permissive policies (replace with proper auth in production)
-- create policy "allow all conversations" on conversations for all using (true);
-- create policy "allow all messages" on messages for all using (true);
-- create policy "allow all documents" on documents for all using (true);
-- create policy "allow all conversation_documents" on conversation_documents for all using (true);
