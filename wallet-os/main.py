import os, time, re
from datetime import datetime, timezone, timedelta
from html import unescape as html_unescape
from collections import defaultdict, deque
from typing import Any
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT=os.path.dirname(os.path.abspath(__file__))
SUPABASE_URL=os.getenv("SUPABASE_URL","").rstrip("/")
SUPABASE_PUBLISHABLE_KEY=os.getenv("SUPABASE_PUBLISHABLE_KEY","")
OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL","").rstrip("/")
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL","gpt-oss:20b")
OLLAMA_API_KEY=os.getenv("OLLAMA_API_KEY","")
WALLET_AUTH_REQUIRED=os.getenv("WALLET_AUTH_REQUIRED","true").lower() not in ("false","0","no")
app=FastAPI(title="WALLET OS API",version="1.0.0")
requests=defaultdict(deque)

class ChatRequest(BaseModel):
 message:str=Field(min_length=1,max_length=4000)
 context:dict[str,Any]=Field(default_factory=dict)
 language:str="ar"

@app.middleware("http")
async def basic_rate_limit(request:Request,call_next):
 if request.url.path=="/api/chat":
  key=request.client.host if request.client else "unknown"; q=requests[key]; now=time.time()
  while q and now-q[0]>60:q.popleft()
  if len(q)>=12: return Response('{"detail":"Rate limit exceeded"}',status_code=429,media_type="application/json")
  q.append(now)
 return await call_next(request)

@app.get("/config.js")
async def config():
 payload={"supabaseUrl":SUPABASE_URL,"supabaseAnonKey":SUPABASE_PUBLISHABLE_KEY}
 import json
 return Response("window.WALLET_CONFIG="+json.dumps(payload)+";",media_type="application/javascript",headers={"Cache-Control":"no-store"})


# Public market data is cached briefly by each serverless instance. No provider key is exposed.
MARKET_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
GOLD_PRICE_URL = "https://api.gold-api.com/price/XAU"
FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rates"

async def cached_market_json(key: str, url: str, ttl: int = 30) -> dict[str, Any]:
 cached = MARKET_CACHE.get(key)
 now = time.time()
 if cached and now - cached[0] < ttl:
  return cached[1]
 async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), follow_redirects=True) as client:
  response = await client.get(url, headers={"Accept":"application/json","User-Agent":"WALLET-OS/1.0 market data"})
  response.raise_for_status()
  payload = response.json()
 if not isinstance(payload, (dict, list)):
  raise HTTPException(502, "أعاد مزود الأسعار استجابة غير متوقعة.")
 if isinstance(payload, dict):
  MARKET_CACHE[key] = (now, payload)
  return payload
 return {"rows": payload}

@app.get("/api/market/gold")
async def market_gold():
 try:
  data = await cached_market_json("gold-xau", GOLD_PRICE_URL, 30)
  price = float(data.get("price", 0))
  updated_at = data.get("updatedAt")
  if price <= 0 or not updated_at:
   raise HTTPException(502, "بيانات الذهب لا تحتوي سعرًا أو وقت تحديث صالحًا.")
  return {
   "symbol": data.get("symbol", "XAU"),
   "name": data.get("name", "Gold"),
   "price_usd_troy_ounce": price,
   "currency": data.get("currency", "USD"),
   "updated_at": updated_at,
   "source": "Gold API",
   "source_url": GOLD_PRICE_URL,
   "troy_ounce_grams": 31.1034768,
  }
 except HTTPException:
  raise
 except (httpx.HTTPError, ValueError, TypeError):
  raise HTTPException(503, "تعذر جلب سعر الذهب العالمي حاليًا. حاول لاحقًا.")

@app.get("/api/market/fx")
async def market_fx(base: str = "USD", quotes: str = "EUR,SAR,AED,YER"):
 base = base.upper().strip()
 if base not in {"USD","EUR","SAR","AED","YER"}:
  raise HTTPException(400, "عملة الأساس غير مدعومة.")
 allowed = {"USD","EUR","SAR","AED","YER"}
 quote_list = sorted({q.strip().upper() for q in quotes.split(",") if q.strip().upper() in allowed and q.strip().upper() != base})
 if not quote_list:
  return {"base": base, "rates": {}, "date": None, "source": "Frankfurter"}
 url = FRANKFURTER_URL + "?base=" + base + "&quotes=" + ",".join(quote_list)
 key = "fx:" + base + ":" + ",".join(quote_list)
 try:
  data = await cached_market_json(key, url, 900)
  rows = data.get("rows") if isinstance(data.get("rows"), list) else data
  rates: dict[str, float] = {}
  rate_date = data.get("date") if isinstance(data, dict) else None
  if isinstance(rows, list):
   for row in rows:
    if not isinstance(row, dict):
     continue
    quote = str(row.get("quote", row.get("currency", ""))).upper()
    value = row.get("rate")
    if quote in quote_list and value is not None:
     rates[quote] = float(value)
     rate_date = max(str(rate_date or ""), str(row.get("date") or ""))
  elif isinstance(rows, dict):
   candidate = rows.get("rates", rows)
   if isinstance(candidate, dict):
    for quote, value in candidate.items():
     if quote.upper() in quote_list and isinstance(value, (int,float)):
      rates[quote.upper()] = float(value)
  if not rates:
   raise HTTPException(503, "لم يُرجع مزود أسعار الصرف أسعارًا للعملات المطلوبة.")
  return {"base": base, "rates": rates, "date": rate_date, "source": "Frankfurter", "source_url": "https://frankfurter.dev/"}
 except HTTPException:
  raise
 except (httpx.HTTPError, ValueError, TypeError):
  raise HTTPException(503, "تعذر جلب أسعار الصرف المرجعية حاليًا.")

@app.get("/api/market/aden-fx")
async def market_aden_fx():
 cache_key = "aden-market-fx"
 cached = MARKET_CACHE.get(cache_key)
 now = time.time()
 if cached and now - cached[0] < 300:
  return cached[1]
 source_url = "https://t.me/s/yemensul"
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=6), follow_redirects=True) as client:
   response = await client.get(source_url, headers={"Accept":"text/html","User-Agent":"Mozilla/5.0 (compatible; WALLET-OS/1.0; market-rates)"})
   response.raise_for_status()
  fragments = re.findall(r'<div[^>]*class=["\'][^"\']*tgme_widget_message_text[^"\']*["\'][^>]*>(.*?)</div>', response.text, re.I | re.S)
  if not fragments:
   raise HTTPException(503, "لم يعرض مصدر أسعار عدن منشورات قابلة للقراءة حاليًا.")
  candidates = []
  digit_map = str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫", "0123456789,.")
  for fragment in fragments:
   text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
   text = re.sub(r"<[^>]+>", " ", text)
   text = html_unescape(text).translate(digit_map)
   text = re.sub(r"[ \t]+", " ", text)
   aden_headers = list(re.finditer(r"بتوقيت\s*عدن", text))
   if not aden_headers:
    continue
   aden_text = text[aden_headers[-1].start():]
   aden_text = re.split(r"رابط\s*قناة", aden_text, maxsplit=1)[0]
   def read_rate(action: str, label: str):
    match = re.search(rf"{action}\s*(?:الريال\s*)?{label}[^\d]{{0,80}}(\d[\d,]*(?:\.\d+)?)", aden_text, re.I)
    if not match:
     return None
    return float(match.group(1).replace(",", ""))
   usd_buy = read_rate("شراء", "الدولار")
   usd_sell = read_rate("بيع", "الدولار")
   sar_buy = read_rate("شراء", "السعودي")
   sar_sell = read_rate("بيع", "السعودي")
   dates = re.findall(r"(\d{1,2}/\d{1,2}/\d{4})", text)
   if not dates or None in (usd_buy, usd_sell, sar_buy, sar_sell):
    continue
   try:
    rate_date = datetime.strptime(dates[-1], "%d/%m/%Y").date().isoformat()
   except ValueError:
    continue
   if not (500 <= usd_buy <= 3000 and usd_buy <= usd_sell <= 3000 and 100 <= sar_buy <= 800 and sar_buy <= sar_sell <= 800):
    continue
   time_match = re.search(r"(\d{1,2}:\d{2})\s*(صباح|مساء)?", aden_text)
   candidates.append({
    "date": rate_date,
    "time": ((time_match.group(1) + (" " + time_match.group(2) if time_match.group(2) else "")) if time_match else None),
    "rates": {
     "USD": {"buy": usd_buy, "sell": usd_sell, "mid": (usd_buy + usd_sell) / 2},
     "SAR": {"buy": sar_buy, "sell": sar_sell, "mid": (sar_buy + sar_sell) / 2}
    }
   })
  if not candidates:
   raise HTTPException(503, "تعذر استخراج أسعار الدولار والسعودي لمدينة عدن من آخر منشورات المصدر.")
  latest = max(candidates, key=lambda row: row["date"])
  local_date = (datetime.now(timezone.utc) + timedelta(hours=3)).date()
  payload = {
   "market": "Aden",
   "banknote_type": "new",
   "currency": "YER",
   "date": latest["date"],
   "time": latest["time"],
   "fetched_at": datetime.now(timezone.utc).isoformat(),
   "is_stale": latest["date"] < local_date.isoformat(),
   "rates": latest["rates"],
   "source": "YemenSul – public Telegram channel",
   "source_url": source_url,
   "note": "أسعار سوقية استرشادية للأوراق النقدية الجديدة في عدن؛ قد تختلف حسب الصراف ووقت التنفيذ."
  }
  MARKET_CACHE[cache_key] = (now, payload)
  return payload
 except HTTPException:
  raise
 except (httpx.HTTPError, ValueError, TypeError):
  raise HTTPException(503, "تعذر جلب أسعار سوق عدن حاليًا من مصدر YemenSul. حاول لاحقًا.")

@app.get("/api/health")
async def health():
 ollama_reachable=False
 model_available=False
 if OLLAMA_BASE_URL and OLLAMA_API_KEY:
  try:
   async with httpx.AsyncClient(timeout=httpx.Timeout(4,connect=2)) as client:
    response=await client.get(OLLAMA_BASE_URL+"/api/tags",headers={"Authorization":"Bearer "+OLLAMA_API_KEY})
    ollama_reachable=response.status_code==200
    if ollama_reachable:
     models=(response.json().get("models") or [])
     model_available=any(str(m.get("name","")).split(":")[0]==OLLAMA_MODEL.split(":")[0] for m in models)
  except (httpx.HTTPError, ValueError, TypeError):
   ollama_reachable=False
   model_available=False
 return {"ok":True,"supabase_configured":bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY),"ollama_configured":bool(OLLAMA_BASE_URL and OLLAMA_API_KEY),"ollama_reachable":ollama_reachable,"model_available":model_available,"model":OLLAMA_MODEL}

async def verify_user(authorization:str|None):
 if not authorization or not authorization.lower().startswith("bearer "):
  if WALLET_AUTH_REQUIRED: raise HTTPException(401,"سجّل الدخول أولًا.")
  return None
 if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY: raise HTTPException(503,"Supabase غير مهيأ.")
 token=authorization.split(" ",1)[1].strip()
 async with httpx.AsyncClient(timeout=8) as c:
  try:r=await c.get(SUPABASE_URL+"/auth/v1/user",headers={"apikey":SUPABASE_PUBLISHABLE_KEY,"Authorization":"Bearer "+token})
  except httpx.HTTPError: raise HTTPException(503,"تعذر التحقق من جلسة المستخدم.")
 if r.status_code!=200: raise HTTPException(401,"جلسة الدخول غير صالحة أو منتهية.")
 return r.json().get("id")

@app.post("/api/chat")
async def chat(req:ChatRequest,authorization:str|None=Header(default=None)):
 await verify_user(authorization)
 if not OLLAMA_BASE_URL or not OLLAMA_API_KEY: raise HTTPException(503,"مساعد Ollama غير متصل بعد. اضبط عنوان HTTPS ومفتاح الخدمة على الخادم.")
 context=req.context if isinstance(req.context,dict) else {}
 # Send only aggregate totals and a capped, sanitized transaction sample; never send account IDs or auth data.
 txs=context.get("transactions",[]) if isinstance(context.get("transactions",[]),list) else []
 safe=[]
 for t in txs[-60:]:
  if not isinstance(t,dict): continue
  safe.append({k:t.get(k) for k in ("type","amount","currency","category","date")})
 safe_investments=[]
 for item in (context.get("investments",[]) if isinstance(context.get("investments",[]),list) else [])[:30]:
  if not isinstance(item,dict): continue
  meta=item.get("metadata") if isinstance(item.get("metadata"),dict) else {}
  safe_investments.append({"asset_type":str(item.get("asset_type",""))[:30],"name":str(item.get("name",""))[:100],"invested_amount":item.get("invested_amount",0),"current_value":item.get("current_value",0),"currency":str(item.get("currency",""))[:3],"gold_weight_grams":meta.get("weight_grams"),"gold_karat":meta.get("karat")})
 fx=context.get("fx_rates") if isinstance(context.get("fx_rates"),dict) else {}
 safe_fx={str(k)[:3]:v for k,v in fx.items() if k in ("USD","EUR","SAR","AED","YER") and isinstance(v,(int,float))}
 gold=context.get("gold_market") if isinstance(context.get("gold_market"),dict) else None
 safe_gold=None
 if gold:
  safe_gold={"price_usd_troy_ounce":gold.get("price_usd_troy_ounce"),"updated_at":str(gold.get("updated_at",""))[:40],"source":str(gold.get("source",""))[:60]}
 safe_context={"currency":str(context.get("currency","YER"))[:3],"income":context.get("income",0),"expenses":context.get("expenses",0),"net":context.get("net",0),"fx_rates_usd_base":safe_fx,"gold_market":safe_gold,"investments":safe_investments,"transactions":safe}
 system=("أنت WALLET OS، مساعد تحليل مالي. استخدم فقط الأرقام المقدمة ولا تخترع بيانات. وضح العملة وتاريخ أسعار الصرف ومصدرها، وميّز بين أسعار الصرف المرجعية اليومية وسعر السوق النقدي. سعر الذهب الفوري مرجعي بالدولار للأونصة الترويسية، والسعر المحسوب للغرام لا يشمل المصنعية أو الضريبة أو فرق البيع والشراء. لا تستخدم سعر الذهب إذا كان وقت تحديثه غير واضح أو قديمًا. التحويلات ليست دخلا ولا مصروفا. لا تنفذ معاملات أو تدّع تنفيذها. قدم توصيات عملية غير مضمونة النتائج. أجب باللغة العربية." if req.language=="ar" else "You are WALLET OS, a careful personal finance analysis assistant. Use only supplied facts, state currency, FX dates and sources, distinguish daily reference FX from local cash-market rates, identify gold spot as an indicative quote excluding dealer premiums and taxes, never invent data or claim to execute transactions.")
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(180,connect=10)) as c:
   r=await c.post(OLLAMA_BASE_URL+"/api/chat",headers={"Authorization":"Bearer "+OLLAMA_API_KEY,"Content-Type":"application/json"},json={"model":OLLAMA_MODEL,"stream":False,"messages":[{"role":"system","content":system+"\nFinancial data (sanitized): "+__import__("json").dumps(safe_context,ensure_ascii=False)},{"role":"user","content":req.message}]})
  if r.status_code==402:
   raise HTTPException(402,"رفضت Ollama تنفيذ الطلب بسبب حالة الاستخدام أو الفوترة (HTTP 402). افتح https://ollama.com/settings لمراجعة استخدام حسابك وحدود الخطة. قد تكون حصة الاستخدام المجانية للجلسة أو الأسبوع قد استُهلكت؛ انتظر إعادة ضبطها أو راجع خيارات حسابك. لا حاجة إلى إنشاء مفتاح جديد ما دام فحص الاتصال ناجحًا.")
  if r.status_code==401:
   raise HTTPException(502,"رفضت Ollama مفتاح API (HTTP 401). تحقق من المفتاح المحفوظ في Vercel.")
  if r.status_code==403:
   raise HTTPException(502,"حساب Ollama غير مخوّل لاستخدام هذا النموذج (HTTP 403). راجع صلاحيات النموذج والخطة.")
  if r.status_code==404:
   raise HTTPException(502,"النموذج المحدد غير متاح لخدمة Ollama (HTTP 404). تحقق من اسم النموذج في إعدادات Vercel.")
  if r.status_code==429:
   raise HTTPException(429,"وصلت إلى حد الطلبات المؤقت في Ollama (HTTP 429). انتظر قليلًا ثم حاول مجددًا.")
  if r.status_code>=400:
   raise HTTPException(502,"أعادت خدمة Ollama خطأ HTTP "+str(r.status_code)+". حاول مجددًا لاحقًا.")
  data=r.json(); answer=(data.get("message") or {}).get("content","").strip()
  if not answer: raise HTTPException(502,"لم يُرجع النموذج إجابة.")
  return {"ok":True,"model":OLLAMA_MODEL,"content":answer}
 except httpx.TimeoutException: raise HTTPException(504,"استغرق النموذج وقتًا طويلًا. حاول مجددًا.")
 except HTTPException: raise
 except Exception: raise HTTPException(502,"تعذر الاتصال بخدمة Ollama الآمنة.")

@app.get("/")
async def index(): return FileResponse(os.path.join(ROOT,"index.html"))
@app.get("/logo.svg")
async def logo(): return FileResponse(os.path.join(ROOT,"logo.svg"),media_type="image/svg+xml")
