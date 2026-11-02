create extension if not exists pgcrypto;
create table if not exists public.transactions (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 type text not null check (type in ('income','expense','transfer')),
 amount numeric(18,2) not null check (amount > 0),
 currency text not null check (currency in ('YER','SAR','USD','AED')),
 title text not null,
 category text not null default 'عام',
 transaction_date date not null default current_date,
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists transactions_user_date_idx on public.transactions(user_id, transaction_date desc);
alter table public.transactions enable row level security;
drop policy if exists "Users can read their transactions" on public.transactions;
create policy "Users can read their transactions" on public.transactions for select to authenticated using (auth.uid() = user_id);
drop policy if exists "Users can insert their transactions" on public.transactions;
create policy "Users can insert their transactions" on public.transactions for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "Users can update their transactions" on public.transactions;
create policy "Users can update their transactions" on public.transactions for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "Users can delete their transactions" on public.transactions;
create policy "Users can delete their transactions" on public.transactions for delete to authenticated using (auth.uid() = user_id);
