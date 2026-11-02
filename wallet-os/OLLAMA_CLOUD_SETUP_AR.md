# تشغيل Ollama مع WALLET OS على خادم سحابي آمن

## البنية
- يستضيف Vercel واجهة WALLET OS وواجهة FastAPI.
- يعمل Ollama على VPS أو جهاز دائم التشغيل؛ لا تثبته داخل Vercel Functions.
- يجب نشر Ollama خلف HTTPS Gateway محمي بمفتاح خدمة أو Cloudflare Access.
- لا تفتح المنفذ 11434 مباشرة للإنترنت، ولا تضع مفتاح الخدمة في الواجهة.

## إعداد الخادم
1. اختر VPS دائم التشغيل بذاكرة مناسبة للنموذج؛ نموذج 4B يحتاج ذاكرة عدة GB على الأقل، والأداء يتوقف على العتاد.
2. ثبّت Ollama من الموقع الرسمي ثم نفّذ: `ollama pull qwen3.5:4b`.
3. اختبر محليًا: `ollama run qwen3.5:4b`.
4. اجعل خدمة Ollama تستمع على loopback أو شبكة داخلية فقط.
5. ضع أمامها بوابة HTTPS تتحقق من رمز وصول قوي، ثم تمرر طلبات /api/chat إلى Ollama. اختبر من خارج الخادم أن الاتصال غير المصرح به مرفوض.
6. خزّن عنوان البوابة HTTPS ورمزها في Vercel Environment Variables باسم `OLLAMA_BASE_URL` و`OLLAMA_API_KEY`، واسم النموذج في `OLLAMA_MODEL`.

## متغيرات Vercel
- `SUPABASE_URL`: عنوان مشروع WALLET OS المستقل.
- `SUPABASE_PUBLISHABLE_KEY`: مفتاح النشر العام من المشروع نفسه.
- `WALLET_AUTH_REQUIRED=true`.
- `OLLAMA_BASE_URL=https://عنوان-بوابة-خاصة`.
- `OLLAMA_API_KEY`: رمز وصول خادم-إلى-خادم.
- `OLLAMA_MODEL=qwen3.5:4b`.

لا تستخدم مفتاح Supabase service_role في المتصفح. بعد إضافة متغيرات البيئة، أعد النشر ثم اختبر `/api/health` وتسجيل الدخول وسؤالًا عربيًا فعليًا في المساعد. لا يعتبر الربط فعالًا قبل نجاح اختبار مباشر للنموذج.
