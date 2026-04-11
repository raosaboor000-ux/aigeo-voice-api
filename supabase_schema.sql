-- Run this in Supabase SQL Editor (Dashboard → SQL → New query)

create table if not exists public.conversation_messages (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists conversation_messages_session_id_idx
  on public.conversation_messages (session_id);

create index if not exists conversation_messages_session_created_idx
  on public.conversation_messages (session_id, created_at);

-- Server uses service role key and bypasses RLS. If you use the anon key from the browser,
-- enable RLS and add policies (not required for backend-only access with service role).
