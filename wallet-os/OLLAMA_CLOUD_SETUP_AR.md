# ربط وكيل WALLET OS بـ Ollama

## أولًا: Ollama Cloud (لا يحتاج VPS)
ملف Vercel مهيأ حاليًا:
- `OLLAMA_BASE_URL=https://ollama.com`
- `OLLAMA_MODEL=gpt-oss:20b`

بقي مفتاح API، لأنه مرتبط بحساب Ollama الخاص بك ولا يمكن توليده نيابة عنك.

1. افتح https://ollama.com/settings/keys وأنشئ API key.
2. افتح Vercel → مشروع wallet-os → Settings → Environment Variables.
3. أضف `OLLAMA_API_KEY` كمتغير **Sensitive/Encrypted** إلى Production وPreview وDevelopment.
4. لا تضع المفتاح في GitHub أو index.html أو رسائل المحادثة.
5. أعد النشر.
6. اختبر `https://wallet-os-ibrahimalcendee-4539.vercel.app/api/health`. المطلوب أن يكون `ollama_reachable=true` و`model_available=true`.
7. جرّب الوكيل بسؤال عام لا يتضمن بيانات مالية حساسة أولًا.

### ملاحظة التكلفة
Ollama Pay as you go لا يتطلب اشتراكًا شهريًا، لكنه يحاسب طلبات النماذج السحابية حسب عدد الرموز. لذلك ليس API مجانيًا بلا حدود. `gpt-oss:20b` خيار أقل تكلفة من النماذج الأكبر وفق جدول الأسعار المنشور، لكن لا ترسل طلبات إلا بعد الاطلاع على أسعار النموذج وحدود الاستخدام:
https://ollama.com/pricing

## ثانيًا: تشغيل محلي على جهاز تملكه
يمكن تشغيل Ollama محليًا دون دفع رسوم استخدام سحابية. يلزم بقاء الجهاز متصلًا بالإنترنت والعمل حتى يصل إليه Vercel. لا تعرّض المنفذ 11434 للعامة؛ استخدم Docker Compose وCaddy في مجلد `ollama/` وبوابة HTTPS مع Bearer key. تتحمل استهلاك الجهاز والكهرباء والإنترنت.

## ثالثًا: GitHub Actions
ملف `.github/workflows/ollama-smoke.yml` اختبار مؤقت ينزل Ollama والنموذج على Runner ويجري استدلالًا عربيًا ثم يوقف الحاوية. لا يوفر GitHub Actions خادمًا دائمًا يمكن ربطه بالوكيل بعد انتهاء المهمة.

## التحقق
واجهة الوكيل تستدعي `/api/health` وتعرض حالتين منفصلتين: وصول الخادم، وتوفر النموذج المحدد. لا تظهر الحالة "متصل والنموذج جاهز" حتى يعود الاثنان صحيحين. لا تشارك API key مع أي مستخدم أو تضعها في مستودع المشروع.
