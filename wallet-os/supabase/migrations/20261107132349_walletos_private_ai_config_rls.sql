-- Defense in depth: enable RLS on the private schema configuration table as well.
alter table private.user_ai_provider_configs enable row level security;
drop policy if exists user_ai_provider_configs_own on private.user_ai_provider_configs;
create policy user_ai_provider_configs_own on private.user_ai_provider_configs
  for all to authenticated
  using ((select auth.uid())=user_id)
  with check ((select auth.uid())=user_id);
revoke all on schema private from public,anon,authenticated;
revoke all on private.user_ai_provider_configs from public,anon,authenticated;
