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

alter table public.investments
  add column if not exists metadata jsonb not null default '{}'::jsonb;

create table if not exists public.exchange_rates (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  base_currency char(3) not null check (base_currency in ('USD','EUR','SAR','AED','YER')),
  quote_currency char(3) not null check (quote_currency in ('USD','EUR','SAR','AED','YER')),
  rate numeric(24,10) not null check (rate > 0),
  rate_date date not null,
  source text not null default 'Frankfurter',
  created_at timestamptz not null default now(),
  unique (user_id, base_currency, quote_currency, rate_date),
  check (base_currency <> quote_currency)
);
create index if not exists exchange_rates_user_date_idx
  on public.exchange_rates(user_id, rate_date desc);
alter table public.exchange_rates enable row level security;
drop policy if exists exchange_rates_own on public.exchange_rates;
create policy exchange_rates_own on public.exchange_rates for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
grant select,insert,update,delete on public.exchange_rates to authenticated;
revoke all on public.exchange_rates from anon;


alter table public.transactions
  add column if not exists account_id uuid references public.accounts(id) on delete set null,
  add column if not exists source_account_id uuid references public.accounts(id) on delete set null,
  add column if not exists destination_account_id uuid references public.accounts(id) on delete set null;

create index if not exists transactions_user_date_idx on public.transactions(user_id,transaction_date desc);
create index if not exists transactions_user_type_idx on public.transactions(user_id,type);
create index if not exists transactions_account_id_idx on public.transactions(account_id);
create index if not exists transactions_source_account_id_idx on public.transactions(source_account_id);
create index if not exists transactions_destination_account_id_idx on public.transactions(destination_account_id);
create index if not exists accounts_user_idx on public.accounts(user_id);
create index if not exists savings_goals_user_idx on public.savings_goals(user_id);
create index if not exists liabilities_user_idx on public.liabilities(user_id);
create index if not exists investments_user_idx on public.investments(user_id);
create index if not exists budgets_user_idx on public.budgets(user_id);

create or replace function public.validate_transaction_accounts()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $
declare
  source_currency char(3);
  destination_currency char(3);
  linked_currency char(3);
  source_owner uuid;
  destination_owner uuid;
  linked_owner uuid;
begin
  if new.type = 'transfer' then
    if new.account_id is not null then
      raise exception 'لا تربط التحويل بحساب مفرد؛ حدد المصدر والوجهة';
    end if;
    if new.source_account_id is null or new.destination_account_id is null
       or new.source_account_id = new.destination_account_id then
      raise exception 'يجب تحديد حساب مصدر وحساب وجهة مختلفين للتحويل';
    end if;
    select currency, user_id into source_currency, source_owner
      from public.accounts where id = new.source_account_id;
    select currency, user_id into destination_currency, destination_owner
      from public.accounts where id = new.destination_account_id;
    if source_owner is null or destination_owner is null
       or source_owner <> new.user_id or destination_owner <> new.user_id then
      raise exception 'حساب التحويل غير متاح لهذا المستخدم';
    end if;
    if source_currency <> destination_currency or new.currency <> source_currency then
      raise exception 'التحويل يتطلب حسابين بالعملة نفسها';
    end if;
  else
    new.source_account_id := null;
    new.destination_account_id := null;
    if new.account_id is not null then
      select currency, user_id into linked_currency, linked_owner
        from public.accounts where id = new.account_id;
      if linked_owner is null or linked_owner <> new.user_id then
        raise exception 'الحساب غير متاح لهذا المستخدم';
      end if;
      if linked_currency <> new.currency then
        raise exception 'عملة العملية يجب أن تطابق عملة الحساب';
      end if;
    end if;
  end if;
  return new;
end;
$;

drop trigger if exists transactions_validate_accounts on public.transactions;
create trigger transactions_validate_accounts
before insert or update of type, user_id, currency, account_id, source_account_id, destination_account_id
on public.transactions
for each row execute function public.validate_transaction_accounts();

alter table public.transactions
  drop constraint if exists transactions_transfer_accounts_check;
alter table public.transactions
  add constraint transactions_transfer_accounts_check
  check (
    (type = 'transfer' and account_id is null and source_account_id is not null
      and destination_account_id is not null and source_account_id <> destination_account_id)
    or
    (type <> 'transfer' and source_account_id is null and destination_account_id is null)
  );

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


-- Current WALLET OS services schema and per-user AI Vault settings.
-- WALLET OS: per-user AI provider secrets (Supabase Vault) and market snapshots.
create extension if not exists supabase_vault with schema vault;
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.user_ai_provider_configs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  provider text not null check (provider in ('ollama_cloud','openai','openrouter','groq','custom')),
  model text not null check (length(model) between 1 and 160),
  base_url text,
  vault_secret_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (base_url is null or base_url ~* '^https://')
);
revoke all on private.user_ai_provider_configs from public, anon, authenticated;

create or replace function public.walletos_save_ai_config(
  p_provider text,p_model text,p_api_key text default null,p_base_url text default null
)
returns jsonb
language plpgsql security definer set search_path=''
as $$
declare
  v_user uuid := auth.uid();
  v_existing private.user_ai_provider_configs%rowtype;
  v_secret_id uuid;
begin
  if v_user is null then raise exception 'Authentication required' using errcode='28000'; end if;
  if p_provider not in ('ollama_cloud','openai','openrouter','groq','custom') then
    raise exception 'Unsupported AI provider' using errcode='22023';
  end if;
  if p_model is null or length(btrim(p_model)) < 1 or length(p_model) > 160 then
    raise exception 'Invalid model name' using errcode='22023';
  end if;
  if p_base_url is not null and p_base_url <> '' and p_base_url !~* '^https://' then
    raise exception 'Base URL must use HTTPS' using errcode='22023';
  end if;
  if p_provider='custom' and coalesce(p_base_url,'')='' then
    raise exception 'Custom provider requires an HTTPS base URL' using errcode='22023';
  end if;
  select * into v_existing from private.user_ai_provider_configs where user_id=v_user for update;
  if p_api_key is not null and btrim(p_api_key) <> '' then
    if v_existing.vault_secret_id is null then
      v_secret_id := vault.create_secret(p_api_key,'walletos-ai-'||v_user::text,'WALLET OS per-user AI provider key',null);
    else
      perform vault.update_secret(v_existing.vault_secret_id,p_api_key,'walletos-ai-'||v_user::text,'WALLET OS per-user AI provider key',null);
      v_secret_id := v_existing.vault_secret_id;
    end if;
  else
    if v_existing.user_id is not null and v_existing.provider <> p_provider then
      raise exception 'Enter a new API key when switching provider' using errcode='22023';
    end if;
    v_secret_id := v_existing.vault_secret_id;
  end if;
  if v_secret_id is null then raise exception 'Enter an API key for this provider' using errcode='22023'; end if;
  insert into private.user_ai_provider_configs(user_id,provider,model,base_url,vault_secret_id,updated_at)
  values(v_user,p_provider,btrim(p_model),nullif(btrim(p_base_url),''),v_secret_id,now())
  on conflict(user_id) do update set provider=excluded.provider,model=excluded.model,base_url=excluded.base_url,vault_secret_id=excluded.vault_secret_id,updated_at=now();
  return jsonb_build_object('ok',true,'provider',p_provider,'model',btrim(p_model),'base_url',nullif(btrim(p_base_url),''),'has_key',true);
end;
$$;

create or replace function public.walletos_get_ai_config()
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_user uuid := auth.uid(); v_cfg private.user_ai_provider_configs%rowtype;
begin
  if v_user is null then raise exception 'Authentication required' using errcode='28000'; end if;
  select * into v_cfg from private.user_ai_provider_configs where user_id=v_user;
  if v_cfg.user_id is null then return jsonb_build_object('configured',false,'has_key',false); end if;
  return jsonb_build_object('configured',true,'provider',v_cfg.provider,'model',v_cfg.model,'base_url',v_cfg.base_url,'has_key',v_cfg.vault_secret_id is not null);
end;
$$;

create or replace function public.walletos_get_ai_secret()
returns table(provider text,model text,base_url text,api_key text)
language plpgsql security definer set search_path=''
as $$
declare v_user uuid := auth.uid();
begin
  if v_user is null then raise exception 'Authentication required' using errcode='28000'; end if;
  return query
    select c.provider,c.model,c.base_url,d.decrypted_secret
    from private.user_ai_provider_configs c
    left join vault.decrypted_secrets d on d.id=c.vault_secret_id
    where c.user_id=v_user;
end;
$$;

create or replace function public.walletos_clear_ai_config()
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_user uuid := auth.uid();
begin
  if v_user is null then raise exception 'Authentication required' using errcode='28000'; end if;
  delete from private.user_ai_provider_configs where user_id=v_user;
  return jsonb_build_object('ok',true);
end;
$$;

create table if not exists public.market_fx_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  base_currency char(3) not null check (base_currency in ('USD','EUR','SAR','AED','YER')),
  quote_currency char(3) not null check (quote_currency in ('USD','EUR','SAR','AED','YER')),
  rate numeric(24,10) not null check (rate>0),
  rate_date date not null,
  rate_type text not null default 'mid_market' check (rate_type in ('mid_market','official','parallel','manual','indicative')),
  region text not null default 'GLOBAL',
  source text not null,source_url text,
  observed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (base_currency<>quote_currency),
  unique(user_id,base_currency,quote_currency,rate_date,rate_type,region,source)
);
create index if not exists market_fx_snapshots_user_pair_date_idx on public.market_fx_snapshots(user_id,base_currency,quote_currency,rate_date desc);

create table if not exists public.gold_price_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  symbol char(3) not null default 'XAU' check (symbol in ('XAU','XAG')),
  price_usd_troy_ounce numeric(24,8) not null check (price_usd_troy_ounce>0),
  currency char(3) not null default 'USD' check (currency='USD'),
  source text not null,source_url text,
  observed_at timestamptz not null,ingested_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique(user_id,symbol,source,observed_at)
);
create index if not exists gold_price_snapshots_user_observed_idx on public.gold_price_snapshots(user_id,symbol,observed_at desc);

create table if not exists public.market_asset_quotes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  asset_class text not null check (asset_class in ('metal','crypto','stock')),
  symbol text not null,name text,
  price numeric(28,10) not null check(price>0),
  currency char(3) not null,unit text,
  source text not null,source_url text,
  observed_at timestamptz not null,market_state text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(user_id,asset_class,symbol,source,observed_at)
);
create index if not exists market_asset_quotes_user_symbol_time_idx on public.market_asset_quotes(user_id,symbol,observed_at desc);

alter table public.market_fx_snapshots enable row level security;
alter table public.gold_price_snapshots enable row level security;
alter table public.market_asset_quotes enable row level security;
drop policy if exists market_fx_snapshots_own on public.market_fx_snapshots;
create policy market_fx_snapshots_own on public.market_fx_snapshots for all to authenticated
  using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists gold_price_snapshots_own on public.gold_price_snapshots;
create policy gold_price_snapshots_own on public.gold_price_snapshots for all to authenticated
  using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
drop policy if exists market_asset_quotes_own on public.market_asset_quotes;
create policy market_asset_quotes_own on public.market_asset_quotes for all to authenticated
  using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
grant select,insert,update,delete on public.market_fx_snapshots,public.gold_price_snapshots,public.market_asset_quotes to authenticated;
revoke all on public.market_fx_snapshots,public.gold_price_snapshots,public.market_asset_quotes from anon;

revoke execute on function public.walletos_save_ai_config(text,text,text,text) from public,anon;
revoke execute on function public.walletos_get_ai_config() from public,anon;
revoke execute on function public.walletos_get_ai_secret() from public,anon;
revoke execute on function public.walletos_clear_ai_config() from public,anon;
grant execute on function public.walletos_save_ai_config(text,text,text,text) to authenticated;
grant execute on function public.walletos_get_ai_config() to authenticated;
grant execute on function public.walletos_get_ai_secret() to authenticated;
grant execute on function public.walletos_clear_ai_config() to authenticated;

do $$
begin
  if to_regclass('public.financings') is not null then execute 'revoke all on public.financings from anon'; end if;
  if to_regclass('public.financing_payments') is not null then execute 'revoke all on public.financing_payments from anon'; end if;
end $$;


-- Defense in depth: enable RLS on the private schema configuration table as well.
alter table private.user_ai_provider_configs enable row level security;
drop policy if exists user_ai_provider_configs_own on private.user_ai_provider_configs;
create policy user_ai_provider_configs_own on private.user_ai_provider_configs
  for all to authenticated
  using ((select auth.uid())=user_id)
  with check ((select auth.uid())=user_id);
revoke all on schema private from public,anon,authenticated;
revoke all on private.user_ai_provider_configs from public,anon,authenticated;


-- The UI has no delete-key action yet; keep the future helper unavailable over the public RPC surface.
revoke execute on function public.walletos_clear_ai_config() from public, anon, authenticated;
