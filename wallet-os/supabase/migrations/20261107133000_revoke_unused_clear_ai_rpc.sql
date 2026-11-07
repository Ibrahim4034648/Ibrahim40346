-- The UI has no delete-key action yet; keep the future helper unavailable over the public RPC surface.
revoke execute on function public.walletos_clear_ai_config() from public, anon, authenticated;
