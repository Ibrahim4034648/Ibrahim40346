# WALLET OS

واجهة عربية RTL لإدارة السجل المالي، مع تسجيل دخول Supabase، ورسوم تفاعلية، وواجهة مساعدة قابلة للربط بـ Ollama.

## النشر على Vercel
- المستودع: Ibrahim4034648/Ibrahim40346
- Root Directory: wallet-os
- Framework: FastAPI (أو Other مع إعدادات vercel.json الموجودة)
- أضف المتغيرات للبيئتين Production وPreview:
  - SUPABASE_URL
  - SUPABASE_PUBLISHABLE_KEY (مفتاح publishable/anon فقط؛ لا تستخدم service_role)
  - WALLET_AUTH_REQUIRED=true
  - OLLAMA_BASE_URL (عنوان HTTPS للبوابة، وليس عنوان Ollama الداخلي)
  - OLLAMA_API_KEY (نفس السر على خادم Ollama)
  - OLLAMA_MODEL=qwen3.5:4b
- أعد النشر بعد تغيير المتغيرات، ثم اختبر /api/health وتسجيل الدخول والمزامنة.

## Supabase
نفّذ supabase/schema.sql في SQL Editor للمشروع المخصص. الجداول محمية بسياسات RLS. عمليات النسخة التجريبية تحفظ في localStorage بمفتاح مستقل عن كل مستخدم مسجل.

## Ollama
GitHub يحفظ ملفات المشروع ولا يشغّل خدمات طويلة الأمد، كما أن Vercel Functions ليست مضيفًا دائمًا لنموذج Ollama. مجلد ollama/ يحتوي Docker Compose لتشغيل Ollama على VPS مستقل خلف Caddy مع HTTPS ومفتاح Bearer. راجع OLLAMA_CLOUD_SETUP_AR.md وollama/README_AR.md. لا ترفع ملف .env الحقيقي إلى المستودع.

## حدود النسخة الحالية
- لا تجمع المنصة عملات مختلفة بسعر صرف تخميني. كل عملية تحتفظ بقيمتها وعملتها الأصلية، والإجماليات تحسب العملة المختارة فقط.
- التحويلات نوع مستقل حاليًا لكنها لا تنقل الرصيد بين حسابين؛ يلزم إضافة حساب مصدر ووجهة قبل اعتماد أرصدة الحسابات.
- وحدات الحسابات والميزانيات والديون والادخار والاستثمار ما زالت أولية وليست دفاتر محاسبية مكتملة.
- محددات الطلب الحالية للمساعد داخل ذاكرة كل نسخة من الخادم؛ يلزم WAF أو حد استخدام موزع قبل إطلاق عام واسع.
