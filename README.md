# WALLET OS

Personal finance workspace with an Arabic-first interface, 11 finance modules, Supabase cloud sync with per-user Row Level Security, and an Ollama-powered finance analysis agent.

**Application source:** [wallet-os/](./wallet-os/)  
**Setup guide:** [wallet-os/README.md](./wallet-os/README.md)  
**Database schema:** [wallet-os/supabase/schema.sql](./wallet-os/supabase/schema.sql)  
**Ollama cloud setup:** [wallet-os/OLLAMA_CLOUD_SETUP_AR.md](./wallet-os/OLLAMA_CLOUD_SETUP_AR.md)

Ollama runs on a separate secured HTTPS host; it is not bundled into Vercel Functions or this repository. Model weights are downloaded directly by Ollama on the model host.
