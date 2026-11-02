# خادم Ollama الآمن لـ WALLET OS

يُشغّل هذا المجلد Ollama في Docker خلف Caddy. لا يُنشر منفذ 11434 على الإنترنت. تقبل البوابة طلبات API فقط مع Bearer key مطابق، ويصدر Caddy شهادة HTTPS تلقائيًا بعد صحة DNS وفتح المنفذين 80 و443.

ابدأ بنسخ .env.example إلى .env على VPS، ثم اتبع wallet-os/OLLAMA_CLOUD_SETUP_AR.md. ضع النطاق والمفتاح الحقيقيين على الخادم فقط، ولا ترفع ملف .env إلى GitHub.
