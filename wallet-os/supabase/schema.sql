-- WALLET OS cloud schema (dedicated Supabase project only)
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default 'WALLET OS User',
  preferred_language text not null default 'ar' check (preferred_language in ('ar','en')),
  theme text not null default 'system' check (theme in ('light','dark','system')),
  base_currency text not null default 'YER' check (base_currency in ('YER','SAR','USD','AED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null check (type in ('income','expense','transfer')),
  amount numeric(20,4) not null check (amount > 0),
  currency char(3) not null check (currency in ('YER','SAR','USD','AED')),
  title text not null,
  category text not null default 'عام',
  transaction_date date not null default current_date,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.accounts (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,
 account_type text not null default 'cash' check(account_type in ('cash','bank','wallet','savings','other')),
 currency char(3) not null default 'YER' check(currency in ('YER','SAR','USD','AED')),
 opening_balance numeric(20,4) not null default 0,
 created_at timestamptz not null default now()
);
create table if not exists public.savings_goals (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,
 target_amount numeric(20,4) not null check(target_amount>0),
 current_amount numeric(20,4) not null default 0 check(current_amount>=0),
 currency char(3) not null default 'YER' check(currency in ('YER','SAR','USD','AED')),
 target_date date,
 created_at timestamptz not null default now()
);
create table if not exists public.liabilities (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,
 original_amount numeric(20,4) not null check(original_amount>=0),
 remaining_amount numeric(20,4) not null check(remaining_amount>=0),
 currency char(3) not null default 'YER' check(currency in ('YER','SAR','USD','AED')),
 due_date date,
 created_at timestamptz not null default now()
);
create table if not exists public.investments (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,
 asset_type text not null default 'other',
 invested_amount numeric(20,4) not null default 0 check(invested_amount>=0),
 current_value numeric(20,4) not null default 0 check(current_value>=0),
 currency char(3) not null default 'YER' check(currency in ('YER','SAR','USD','AED')),
 created_at timestamptz not null default now()
);
create table if not exists public.budgets (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 name text not null,
 category text not null default '*',
 amount numeric(20,4) not null check(amount>0),
 currency char(3) not null default 'YER' check(currency in ('YER','SAR','USD','AED')),
 period text not null default 'monthly' check(period in ('weekly','monthly','yearly')),
 created_at timestamptz not null default now()
);

create index if not exists transactions_user_date_idx on public.transactions(user_id,transaction_date desc);
create index if not exists transactions_user_type_idx on public.transactions(user_id,type);
create index if not exists accounts_user_idx on public.accounts(user_id);

alter table public.profiles enable row level security;
alter table public.transactions enable row level security;
alter table public.accounts enable row level security;
alter table public.savings_goals enable row level security;
alter table public.liabilities enable row level security;
alter table public.investments enable row level security;
alter table public.budgets enable row level security;

drop policy if exists profiles_select_own on public.profiles;
drop policy if exists profiles_insert_own on public.profiles;
drop policy if exists profiles_update_own on public.profiles;
create policy profiles_select_own on public.profiles for select to authenticated using ((select auth.uid())=id);
create policy profiles_insert_own on public.profiles for insert to authenticated with check ((select auth.uid())=id);
create policy profiles_update_own on public.profiles for update to authenticated using ((select auth.uid())=id) with check ((select auth.uid())=id);

drop policy if exists transactions_own on public.transactions;
create policy transactions_own on public.transactions for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists accounts_own on public.accounts;
create policy accounts_own on public.accounts for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists savings_goals_own on public.savings_goals;
create policy savings_goals_own on public.savings_goals for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists liabilities_own on public.liabilities;
create policy liabilities_own on public.liabilities for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists investments_own on public.investments;
create policy investments_own on public.investments for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists budgets_own on public.budgets;
create policy budgets_own on public.budgets for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);

grant select,insert,update,delete on public.transactions,public.accounts,public.savings_goals,public.liabilities,public.investments,public.budgets,public.profiles to authenticated;
revoke all on public.transactions,public.accounts,public.savings_goals,public.liabilities,public.investments,public.budgets,public.profiles from anon;
