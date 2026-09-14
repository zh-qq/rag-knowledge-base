-- 在 Supabase Dashboard 的 SQL Editor 中执行本文件。
-- 浏览器不直接访问这些表；服务端使用 SUPABASE_SECRET_KEY 访问。

create table if not exists public.knowledge_bases (
  id bigint generated always as identity primary key,
  name text not null unique check (char_length(trim(name)) between 1 and 50),
  created_at timestamptz not null default now()
);

create table if not exists public.documents (
  id bigint generated always as identity primary key,
  knowledge_base_id bigint not null references public.knowledge_bases(id) on delete cascade,
  source_file text not null check (char_length(source_file) between 1 and 255),
  created_at timestamptz not null default now()
);

create index if not exists documents_knowledge_base_id_idx
  on public.documents (knowledge_base_id);

create table if not exists public.document_chunks (
  id bigint generated always as identity primary key,
  document_id bigint not null references public.documents(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null,
  embedding jsonb not null check (jsonb_typeof(embedding) = 'array')
);

create index if not exists document_chunks_document_id_idx
  on public.document_chunks (document_id);

alter table public.knowledge_bases enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;

-- 服务端 Secret Key 对应 service_role；浏览器没有表访问权限。
grant usage on schema public to service_role;
grant select, insert, update, delete on table public.knowledge_bases, public.documents, public.document_chunks to service_role;
grant usage, select on all sequences in schema public to service_role;
