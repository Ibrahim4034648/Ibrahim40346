# WALLET OS

منصة إدارة مالية شخصية بواجهة عربية RTL. صفحة الاستقبال منفصلة عن صفحة المصادقة، ولا توجد بيانات تجريبية أو زر Demo. بعد تسجيل الدخول تُقرأ وتُكتب السجلات إلى مشروع Supabase المخصص وفق سياسات RLS.

## بنية المشروع
- `index.html`: صفحة ترحيبية، تسجيل/إنشاء حساب، لوحة مالية وأقسام CRUD.
- `main.py`: FastAPI config/auth checks وواجهة المساعد.
- `supabase/schema.sql`: المخطط الكامل، سياسات RLS، روابط الحسابات، والتحقق من التحويلات.
- `ollama/`: Docker Compose وCaddy لتشغيل Ollama على خادم مستقل خلف HTTPS.
- `.github/workflows/wallet-os-ci.yml`: فحص شيفرة Python وJavaScript وDocker Compose.
- `.github/workflows/ollama-smoke.yml`: تشغيل Ollama مؤقتًا على GitHub Actions لفحص النموذج.

## Supabase
المشروع المتصل:
- Project: `wallet-os`
- Region: `eu-central-1`
- URL: `https://kdpwhpencwqftplqvrxl.supabase.co`

تتطلب المنصة متغيرات Vercel التالية في Production وPreview:
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` — مفتاح publishable/anon فقط، لا تستخدم `service_role`.
- `WALLET_AUTH_REQUIRED=true`
- `OLLAMA_BASE_URL` (اختياري حتى تشغيل خادم مستقل)
- `OLLAMA_API_KEY` (اختياري حتى تشغيل خادم مستقل)
- `OLLAMA_MODEL=qwen3.5:4b`

تُطبق RLS على جميع جداول البيانات. كل سجل مرتبط بـ `auth.uid()`. معاملات الدخل والمصروف يمكن ربطها بحساب؛ التحويل يتطلب حسابي مصدر ووجهة للمستخدم نفسه وبالعملة نفسها. لا تجمع المنصة عملات مختلفة بسعر صرف غير موثق.

### عنوان عودة البريد
في Supabase Dashboard افتح Authentication → URL Configuration:
- Site URL: `https://wallet-os-ibrahimalcendee-4539.vercel.app`
- Redirect URLs: `https://wallet-os-ibrahimalcendee-4539.vercel.app/**`

يستخدم الكود `emailRedirectTo: window.location.origin` في التسجيل وإعادة تعيين كلمة المرور؛ يجب أن يكون نطاق الإنتاج في قائمة Redirect URLs وإلا قد لا تعود رسالة التأكيد إلى التطبيق.

## Vercel
المشروع الحالي:
- Project: `wallet-os`
- Root Directory: `wallet-os`
- Framework: FastAPI
- Production URL: `https://wallet-os-ibrahimalcendee-4539.vercel.app`
- Region: `fra1`

تم نشر النسخة الأخيرة عبر Vercel API من لقطة ملفات GitHub. ربط GitHub التلقائي لم يكتمل بعد؛ يلزم إضافة GitHub كـ Login Connection في Vercel Account Settings → Authentication، ثم Project Settings → Git وربط `Ibrahim4034648/Ibrahim40346`. بعد ذلك ينشر Vercel تلقائيًا مع كل push إلى فرع الإنتاج `main`.

## Ollama
GitHub Actions يستطيع تشغيل Ollama مؤقتًا ضمن runner عام؛ لأن هذا المستودع Public، فإن standard hosted runners مجانية حسب سياسة GitHub. ملف `.github/workflows/ollama-smoke.yml` ينزّل `qwen3.5:0.8b` وينفذ طلبًا عربيًا ثم يوقف الحاوية. **هذا فحص مؤقت وليس خادمًا دائمًا**: يتم إنهاء runner بعد نهاية المهمة، فلا يمكن وضع عنوان runner في `OLLAMA_BASE_URL` لتشغيل مساعد الإنتاج.

لتشغيل مساعد Vercel طوال الوقت، شغّل `wallet-os/ollama` على جهاز دائم التشغيل أو VPS، واتبع `OLLAMA_CLOUD_SETUP_AR.md`. لا تعرض 11434 للإنترنت، ولا ترفع ملف `.env` الحقيقي أو أي مفتاح سرّي إلى GitHub.

## حدود النسخة الحالية
- لا توجد بيانات تجريبية في الواجهة أو قاعدة البيانات.
- الأرصدة تُشتق من الرصيد الافتتاحي والعمليات المرتبطة بالحساب. العمليات غير المرتبطة تظهر ضمن إجمالي الدخل/المصروفات ولا تؤثر في رصيد حساب معين.
- التحويلات لا تُجرى بين عملتين مختلفتين؛ لا يوجد سعر صرف تلقائي.
- هذه أداة لإدارة السجلات وليست خدمة مصرفية أو تنفيذًا فعليًا للمدفوعات.
