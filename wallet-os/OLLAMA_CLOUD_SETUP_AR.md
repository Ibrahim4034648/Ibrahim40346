# إعداد خادم Ollama لـ WALLET OS

## لماذا خادم مستقل؟
GitHub مستودع للشيفرة وليس خادم تشغيل. كذلك Vercel Functions ليست مناسبة لاستضافة نموذج Ollama دائمًا. شغّل Ollama على VPS Linux مع Docker، واستخدم Caddy كبوابة HTTPS ومصادقة Bearer. صورة Docker الرسمية من Ollama متاحة، ونموذج qwen3.5:4b موجود في مكتبة Ollama الرسمية.
- وثائق Docker: https://docs.ollama.com/docker
- النموذج: https://ollama.com/library/qwen3.5:4b

## المتطلبات
- VPS Linux مع Docker Engine وDocker Compose Plugin.
- ذاكرة وقرص كافيان للنموذج؛ ملف النموذج يقارب 3.4–4 GB، وتحتاج ذاكرة إضافية وقت التشغيل.
- نطاق DNS يشير إلى عنوان الخادم، مثل ai.example.com.
- السماح بالاتصال الوارد إلى المنفذين TCP 80 و443 فقط. لا تفتح 11434.

## خطوات التشغيل
1. انسخ مجلد wallet-os/ollama إلى الخادم.
2. انسخ .env.example إلى .env.
3. عيّن OLLAMA_DOMAIN إلى نطاقك الحقيقي، وACME_EMAIL إلى بريدك، وأنشئ سرًا عشوائيًا بالأمر: openssl rand -hex 32 ثم ضعه في OLLAMA_API_KEY.
4. شغّل الخدمات: docker compose up -d ollama caddy
5. نزّل النموذج: docker compose exec ollama ollama pull qwen3.5:4b
6. تحقق من تنزيله: docker compose exec ollama ollama list
7. اختبر البوابة من جهاز خارجي: curl -i https://DOMAIN/api/tags -H "Authorization: Bearer YOUR_KEY". يجب أن يكون الطلب دون المفتاح أو بمفتاح خاطئ مرفوضًا.
8. أضف في Vercel: OLLAMA_BASE_URL=https://نطاقك، وOLLAMA_API_KEY=نفس المفتاح، وOLLAMA_MODEL=qwen3.5:4b.
9. أعد نشر Vercel ثم اختبر /api/health؛ ظهور ollama_reachable=true يعني أن بوابة Ollama تستجيب.

## الأمان
- لا تضف ports لـ 11434 في docker-compose؛ Ollama متاح داخليًا فقط.
- لا ترفع ملف .env الحقيقي إلى GitHub، ولا تضع المفتاح في index.html.
- غيّر المفتاح إذا تسرب، واحفظه كمتغير بيئة مشفر في Vercel.
- Caddy يستخرج شهادة HTTPS تلقائيًا بعد أن يشير DNS إلى الخادم وتكون المنافذ 80/443 متاحة.
- راقب استخدام الذاكرة والقرص وحدّث صور Docker دوريًا.

هذا المستودع يجهز ملفات التشغيل فقط؛ لا ينشئ VPS أو يحمّل النموذج على خادم خارجي تلقائيًا. يلزم توفير الخادم والنطاق وتكلفتهما.
