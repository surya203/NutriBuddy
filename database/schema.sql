-- NutriBuddy schema
-- Run once in the Supabase SQL Editor on a new project.
-- Uses the anon key plus the signed-in parent's token.
-- Do not put the service-role key in the app; it bypasses these policies.

-- Uncomment only if you need to rebuild this schema from scratch:
-- drop trigger if exists on_auth_user_created on auth.users;
-- drop function if exists public.handle_new_user();
-- drop table if exists public.quiz_attempts cascade;
-- drop table if exists public.chat_messages cascade;
-- drop table if exists public.children cascade;
-- drop table if exists public.parents cascade;

-- ----------------------------------------------------------------
-- Tables
-- ----------------------------------------------------------------

create table public.parents (
  id uuid primary key references auth.users (id) on delete cascade,
  name text not null default '',
  email text not null default '',
  created_at timestamptz not null default now()
);

create table public.children (
  id uuid primary key default gen_random_uuid(),
  parent_id uuid not null references public.parents (id) on delete cascade,
  nickname text not null check (char_length(btrim(nickname)) > 0),
  age integer not null check (age between 7 and 9),
  created_at timestamptz not null default now()
);

create table public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  child_id uuid not null references public.children (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  message text not null check (char_length(message) > 0),
  created_at timestamptz not null default now()
);

create table public.quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  child_id uuid not null references public.children (id) on delete cascade,
  topic text not null check (char_length(btrim(topic)) > 0),
  score integer not null check (score >= 0),
  total_questions integer not null check (total_questions > 0),
  created_at timestamptz not null default now(),
  constraint quiz_attempts_score_within_total check (score <= total_questions)
);

-- ----------------------------------------------------------------
-- Indexes
-- ----------------------------------------------------------------

create index children_parent_id_idx
  on public.children (parent_id);

create index chat_messages_child_id_created_at_idx
  on public.chat_messages (child_id, created_at);

create index quiz_attempts_child_id_created_at_idx
  on public.quiz_attempts (child_id, created_at);

create index quiz_attempts_child_id_topic_idx
  on public.quiz_attempts (child_id, topic);

-- ----------------------------------------------------------------
-- Signup: create the parent profile from Supabase Auth
-- ----------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.parents (id, name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'name', ''),
    coalesce(new.email, '')
  );
  return new;
end;
$$;

revoke all on function public.handle_new_user() from public;
revoke all on function public.handle_new_user() from anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- ----------------------------------------------------------------
-- Row Level Security
-- A parent can only see and change their own row and their own children.
-- ----------------------------------------------------------------

alter table public.parents enable row level security;
alter table public.children enable row level security;
alter table public.chat_messages enable row level security;
alter table public.quiz_attempts enable row level security;

create policy parents_select_own
  on public.parents
  for select
  to authenticated
  using (id = auth.uid());

create policy parents_update_own
  on public.parents
  for update
  to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy children_select_own
  on public.children
  for select
  to authenticated
  using (parent_id = auth.uid());

create policy children_insert_own
  on public.children
  for insert
  to authenticated
  with check (parent_id = auth.uid());

create policy children_update_own
  on public.children
  for update
  to authenticated
  using (parent_id = auth.uid())
  with check (parent_id = auth.uid());

create policy children_delete_own
  on public.children
  for delete
  to authenticated
  using (parent_id = auth.uid());

create policy chat_messages_select_own
  on public.chat_messages
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.children
      where children.id = chat_messages.child_id
        and children.parent_id = auth.uid()
    )
  );

create policy chat_messages_insert_own
  on public.chat_messages
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.children
      where children.id = chat_messages.child_id
        and children.parent_id = auth.uid()
    )
  );

create policy quiz_attempts_select_own
  on public.quiz_attempts
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.children
      where children.id = quiz_attempts.child_id
        and children.parent_id = auth.uid()
    )
  );

create policy quiz_attempts_insert_own
  on public.quiz_attempts
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.children
      where children.id = quiz_attempts.child_id
        and children.parent_id = auth.uid()
    )
  );

-- ----------------------------------------------------------------
-- Grants
-- The parent row is inserted by the signup trigger, not by the client.
-- Chat and quiz rows are append-only from the app.
-- ----------------------------------------------------------------

grant select, update on public.parents to authenticated;
grant select, insert, update, delete on public.children to authenticated;
grant select, insert on public.chat_messages to authenticated;
grant select, insert on public.quiz_attempts to authenticated;
