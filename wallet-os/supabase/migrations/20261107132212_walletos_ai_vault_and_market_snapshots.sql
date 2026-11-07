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
