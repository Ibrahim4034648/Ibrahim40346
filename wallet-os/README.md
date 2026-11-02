# WALLET OS

منصة إدارة مالية شخصية بواجهة عربية RTL. صفحة الاستقبال منفصلة عن صفحة المصادقة، ولا توجد بيانات تجريبية أو زر Demo. بعد تسجيل الدخول تُقرأ وتُكتب السجلات إلى مشروع Supabase المخصص وفق سياسات RLS.

## بنية المشروع
- `index.html`: صفحة ترحيبية، تسجيل/إنشاء حساب، لوحة مالية وأقسام CRUD، وضع فاتح/داكن، وقائمة جانبية قابلة للطي.
- `main.py`: FastAPI config/auth checks، وكيل Ollama، ومصادر أسعار الصرف والذهب.
- `supabase/schema.sql`: المخطط الكامل، سياسات RLS، روابط الحسابات، أسعار صرف خاصة بكل مستخدم، وبيانات الذهب.
- `ollama/`: ملفات Docker/Caddy لتشغيل Ollama على جهاز أو VPS خاص خلف HTTPS.
- `.github/workflows/wallet-os-ci.yml`: فحوص الشيفرة.
- `.github/workflows/ollama-smoke.yml`: اختبار Ollama مؤقت داخل GitHub Actions فقط.

## Supabase
المشروع المتصل:
- Project: `wallet-os`
- Region: `eu-central-1`
- URL: `https://kdpwhpencwqftplqvrxl.supabase.co`

متغيرات Vercel:
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` — مفتاح publishable/anon فقط؛ لا تستخدم `service_role`.
- `WALLET_AUTH_REQUIRED=true`
- `OLLAMA_BASE_URL=https://ollama.com` للربط السحابي، أو عنوان بوابتك الخاصة.
- `OLLAMA_API_KEY` — مفتاح سري لا يوضع في المتصفح أو Git.
- `OLLAMA_MODEL=gpt-oss:20b` — نموذج أقل تكلفة ضمن أمثلة API الرسمية، وتحقق من توفره في حسابك عبر `/api/health`.

جداول المستخدم محمية بسياسات RLS. سجل أسعار الصرف `exchange_rates` مستقل لكل مستخدم وتاريخ ومصدر. عمليات الذهب تحفظ الوزن والعيار وتاريخ الشراء ومصدر سعر السوق ضمن metadata.

## أسعار الصرف والذهب
- أسعار الصرف من Frankfurter API (يومية، mid-market، دون مفتاح API) وتحفظ في Supabase مع تاريخها ومصدرها. هذه ليست أسعار السوق النقدي المحلي؛ أدخل سعرًا يدويًا موثقًا للريال اليمني عند الحاجة.
- الذهب من Gold API عبر `/api/market/gold` بالدولار لكل أونصة ترويسية. يحسب التطبيق سعر الغرام والعيارات 24/22/21/18، ثم يحوله حسب آخر سعر صرف متاح. السعر المرجعي لا يشمل المصنعية أو الضرائب أو هامش التاجر.
- لا تستخدم السعر الآلي كعرض شراء أو بيع نهائي؛ أكد السعر مع التاجر قبل تنفيذ أي صفقة.

## Ollama: سحابي أو محلي
### الخيار الأسهل: Ollama Cloud
أُعدّ مشروع Vercel بعنوان `https://ollama.com`، والنموذج الحالي `gpt-oss:20b`. لإنهاء الربط:
1. أنشئ مفتاحًا من https://ollama.com/settings/keys.
2. في Vercel → Project → Settings → Environment Variables أضف `OLLAMA_API_KEY` بنوع Sensitive/Encrypted لبيئات Production وPreview وDevelopment.
3. لا ترسل المفتاح داخل المحادثة، ولا تحفظه في GitHub أو `index.html`.
4. أعد نشر المشروع.
5. افتح `/api/health`؛ يجب أن يظهر `ollama_reachable: true` و`model_available: true`.
6. اختبر وكيل WALLET OS بسؤال غير حساس أولًا.

**التكلفة:** لا توجد رسوم اشتراك شهرية في خطة Pay as you go، لكن طلبات النماذج السحابية تحاسب بحسب الرموز (tokens)، أي أنها ليست استخدامًا سحابيًا مجانيًا غير محدود. تعرض صفحة Ollama الأسعار حسب النموذج، والخطة لديها حدود تزامن واستخدام. لا ترسل طلبات مالية قبل التأكد من حدود حسابك. يمكن مراجعة الأسعار: https://ollama.com/pricing. النموذج `gpt-oss:20b` أقل تكلفة من نماذج أكبر حسب جدول الأسعار المنشور، لكن الأسعار والحدود تتغير.

### تشغيل محلي دون رسوم استخدام سحابية
يمكن تشغيل Ollama على جهاز تملكه مجانًا من ناحية البرنامج، لكن الجهاز يجب أن يبقى يعمل إذا أردت أن يصل إليه الوكيل من Vercel. لا تشغّل منفذ Ollama 11434 مكشوفًا للعامة؛ استخدم بوابة HTTPS ومفتاح وصول كما هو موضح في `OLLAMA_CLOUD_SETUP_AR.md`. هذه الطريقة قد تستهلك كهرباء/إنترنت وموارد جهازك.

### GitHub Actions
`.github/workflows/ollama-smoke.yml` يشغّل Ollama مؤقتًا لفحص النموذج ثم يغلق Runner. هذا ليس خادمًا دائمًا ولا يصلح عنوانًا لوكيل الإنتاج.

## Vercel
المشروع:
- Project: `wallet-os`
- Root Directory: `wallet-os`
- Framework: FastAPI
- Production URL: `https://wallet-os-ibrahimalcendee-4539.vercel.app`
- Region: `fra1`

إذا لم يكن GitHub Login Connection متصلًا في حساب Vercel، اربط المستودع يدويًا من Project Settings → Git بعد إضافة GitHub من Account Settings → Authentication. حتى ذلك الحين، يمكن نشر النسخ عبر Vercel API من لقطة ملفات GitHub.

## عنوان عودة البريد
في Supabase Dashboard → Authentication → URL Configuration:
- Site URL: `https://wallet-os-ibrahimalcendee-4539.vercel.app`
- Redirect URLs: `https://wallet-os-ibrahimalcendee-4539.vercel.app/**`

## الحدود
- لا توجد بيانات تجريبية في الواجهة أو قاعدة البيانات.
- الأرصدة تُشتق من الرصيد الافتتاحي والعمليات المرتبطة بالحساب.
- التحويلات بين حسابين بالعملة نفسها فقط.
- أسعار الذهب والصرف مرجعية، وليست تنفيذًا فعليًا لصفقة أو تحويل أموال.
