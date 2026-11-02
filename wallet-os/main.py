import os, time, re
from urllib.parse import quote
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
COINGECKO_API_KEY=os.getenv("COINGECKO_API_KEY","")
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

@app.get("/api/market/asset")
async def market_asset(kind: str, symbol: str):
 kind=kind.strip().lower()
 raw_symbol=symbol.strip()
 if kind not in {"metal","crypto","stock"} or not raw_symbol:
  raise HTTPException(400,"نوع الأصل أو الرمز غير صالح.")
 if kind=="metal":
  code=raw_symbol.upper()
  units={"XAU":"troy_ounce","XAG":"troy_ounce","HG":"pound"}
  if code not in units:
   raise HTTPException(400,"رمز المعدن غير مدعوم. استخدم XAU أو XAG أو HG.")
  url="https://api.gold-api.com/price/"+code
  try:
   data=await cached_market_json("asset:"+code,url,30)
   price=float(data.get("price",0))
   updated=data.get("updatedAt") or data.get("updated_at")
   if price<=0 or not updated:
    raise HTTPException(502,"لم يُرجع مزود المعادن سعرًا ووقت تحديث صالحين.")
   return {"kind":"metal","symbol":code,"name":data.get("name",code),"price_usd":price,"currency":"USD","unit":units[code],"updated_at":updated,"source":"Gold API","source_url":url}
  except HTTPException:
   raise
  except (httpx.HTTPError,ValueError,TypeError):
   raise HTTPException(503,"تعذر جلب السعر العالمي للمعدن حاليًا.")
 if kind=="crypto":
  code=raw_symbol.upper()
  if code in {"BTC","ETH"}:
   url="https://api.gold-api.com/price/"+code
   try:
    data=await cached_market_json("asset:"+code,url,30)
    price=float(data.get("price",0));updated=data.get("updatedAt") or data.get("updated_at")
    if price<=0 or not updated: raise HTTPException(502,"بيانات العملة الرقمية غير مكتملة.")
    return {"kind":"crypto","symbol":code,"name":data.get("name",code),"price_usd":price,"currency":"USD","unit":"coin","updated_at":updated,"source":"Gold API","source_url":url}
   except HTTPException: raise
   except (httpx.HTTPError,ValueError,TypeError): raise HTTPException(503,"تعذر جلب سعر العملة الرقمية حاليًا.")
  coin_id=raw_symbol.lower()
  if not re.fullmatch(r"[a-z0-9-]{1,80}",coin_id):
   raise HTTPException(400,"أدخل معرّف CoinGecko للعملة، مثل bitcoin أو solana.")
  if not COINGECKO_API_KEY:
   raise HTTPException(503,"هذا الرمز يحتاج مفتاح CoinGecko Demo محفوظًا في Vercel باسم COINGECKO_API_KEY. يتوفر السعر المباشر حاليًا للبيتكوين BTC والإيثيريوم ETH.")
  url="https://api.coingecko.com/api/v3/simple/price?ids="+quote(coin_id,safe="")+"&vs_currencies=usd&include_last_updated_at=true"
  try:
   headers={"Accept":"application/json","x-cg-demo-api-key":COINGECKO_API_KEY}
   async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=5)) as client:
    response=await client.get(url,headers=headers);response.raise_for_status();payload=response.json()
   row=payload.get(coin_id) or {}
   price=float(row.get("usd",0));updated=row.get("last_updated_at")
   if price<=0 or not updated: raise HTTPException(404,"لم يُعثر على معرّف العملة في CoinGecko.")
   return {"kind":"crypto","symbol":raw_symbol.upper(),"name":coin_id.replace("-"," ").title(),"price_usd":price,"currency":"USD","unit":"coin","updated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(int(updated))),"source":"CoinGecko","source_url":"https://www.coingecko.com/"}
  except HTTPException: raise
  except httpx.HTTPStatusError as exc:
   code=exc.response.status_code
   if code==429: raise HTTPException(429,"بلغت حدود طلبات CoinGecko مؤقتًا.")
   if code in (401,403): raise HTTPException(502,"رفض CoinGecko مفتاح API. راجع COINGECKO_API_KEY في Vercel.")
   if code==404: raise HTTPException(404,"معرّف العملة غير موجود في CoinGecko.")
   raise HTTPException(503,"تعذر جلب سعر العملة من CoinGecko.")
  except (httpx.HTTPError,ValueError,TypeError):
   raise HTTPException(503,"تعذر جلب سعر العملة من CoinGecko.")
 ticker=raw_symbol.upper()
 if not re.fullmatch(r"[A-Z0-9.^=_-]{1,24}",ticker):
  raise HTTPException(400,"رمز السهم غير صالح. أدخل رمز التداول فقط.")
 url="https://query1.finance.yahoo.com/v8/finance/chart/"+quote(ticker,safe="")+"?range=1d&interval=1d"
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=5),follow_redirects=True) as client:
   response=await client.get(url,headers={"Accept":"application/json","User-Agent":"Mozilla/5.0 (compatible; WALLET-OS/1.0)"})
   response.raise_for_status();payload=response.json()
  result=((payload.get("chart") or {}).get("result") or [None])[0]
  if not result: raise HTTPException(404,"لم يُعثر على رمز السهم في مزود بيانات السوق.")
  meta=result.get("meta") or {}
  price=meta.get("regularMarketPrice")
  timestamps=result.get("timestamp") or []
  if not price:
   close=((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
   price=next((v for v in reversed(close) if v is not None),None)
  updated=meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)
  if not price or not updated:
   raise HTTPException(502,"لم تتوفر قيمة سوقية صالحة لهذا السهم.")
  return {"kind":"stock","symbol":ticker,"name":meta.get("longName") or meta.get("shortName") or ticker,"price":float(price),"currency":meta.get("currency") or "USD","unit":"share","updated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(int(updated))),"source":"Yahoo Finance chart feed (غير رسمي)","source_url":"https://finance.yahoo.com/","market_state":meta.get("marketState")}
 except HTTPException: raise
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code==404: raise HTTPException(404,"رمز التداول غير معروف لدى Yahoo Finance.")
  raise HTTPException(503,"تعذر الوصول إلى سعر السهم حاليًا.")
 except (httpx.HTTPError,ValueError,TypeError,KeyError):
  raise HTTPException(503,"تعذر جلب سعر السهم حاليًا.")

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
