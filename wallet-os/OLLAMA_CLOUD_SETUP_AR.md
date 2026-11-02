# تشغيل Ollama مع WALLET OS

## الخيار المجاني على GitHub (اختبار مؤقت فقط)
المستودع Public؛ GitHub يتيح استخدام standard hosted runners مجانًا للمستودعات العامة. يوجد ملف workflow:
`.github/workflows/ollama-smoke.yml`
ويقوم بتشغيل Docker image الرسمية، وتنزيل `qwen3.5:0.8b`، وتنفيذ استدلال عربي، ثم حذف الحاوية عند انتهاء المهمة.

**حد أساسي:** GitHub Actions يشغّل المهمة ثم ينهي runner. لذلك لا يقدم عنوانًا ثابتًا أو خادم Ollama دائمًا يمكن أن تتصل به Vercel بعد انتهاء المهمة. استخدم هذا الاختبار للتحقق من أن Ollama والنموذج يعملان، وليس لاستضافة مساعد الإنتاج. لا أنصح بإنشاء نفق عام من Runner مؤقت إلى بياناتك المالية.

## تشغيل دائم لخدمة المساعد
يحتاج مساعد الإنتاج إلى جهاز أو VPS يعمل باستمرار. يمكن أن يكون جهازًا تملكه ومشغّلًا طوال الوقت، أو خادمًا سحابيًا دائمًا. قبل شراء VPS تحقق من التكلفة والموارد المتاحة. لا تُنشأ خدمة مدفوعة تلقائيًا من هذا المستودع.

## إعداد خادم Ollama
- Docker Compose يشغّل Ollama على شبكة داخلية.
- Caddy يستقبل HTTPS ويتحقق من Bearer key.
- المنفذ 11434 غير منشور للإنترنت.

### المتطلبات
- Linux مع Docker Engine وDocker Compose Plugin.
- ذاكرة/قرص ملائمان للنموذج.
- نطاق DNS يشير إلى الخادم ومنافذ 80 و443 متاحة.

### الخطوات
1. انسخ `wallet-os/ollama` إلى جهاز الخادم.
2. `cp .env.example .env`.
3. أدخل نطاقًا حقيقيًا في `OLLAMA_DOMAIN` وبريدك في `ACME_EMAIL`.
4. أنشئ سرًا: `openssl rand -hex 32` وضع الناتج في `OLLAMA_API_KEY`.
5. شغّل `docker compose up -d ollama caddy`.
6. نزّل النموذج: `docker compose exec ollama ollama pull qwen3.5:4b`.
7. تحقق: `docker compose exec ollama ollama list`.
8. اختبر بوابة HTTPS: `curl -i https://YOUR_DOMAIN/api/tags -H "Authorization: Bearer YOUR_KEY"`.
9. أضف على Vercel:
   - `OLLAMA_BASE_URL=https://YOUR_DOMAIN`
   - `OLLAMA_API_KEY` = نفس السر
   - `OLLAMA_MODEL=qwen3.5:4b`
10. أعد نشر Vercel واختبر `/api/health`؛ يلزم أن يكون `ollama_reachable: true`.

لا تفتح 11434 على الجدار الناري، ولا تحفظ المفتاح في الواجهة أو المستودع. لا ترفع `.env` الحقيقي إلى GitHub.
