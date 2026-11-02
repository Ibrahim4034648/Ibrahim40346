import os, time
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
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL","qwen3.5:4b")
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

@app.get("/api/health")
async def health():
 ollama_reachable=False
 if OLLAMA_BASE_URL and OLLAMA_API_KEY:
  try:
   async with httpx.AsyncClient(timeout=httpx.Timeout(4,connect=2)) as client:
    response=await client.get(OLLAMA_BASE_URL+"/api/tags",headers={"Authorization":"Bearer "+OLLAMA_API_KEY})
    ollama_reachable=response.status_code==200
  except httpx.HTTPError:
   ollama_reachable=False
 return {"ok":True,"supabase_configured":bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY),"ollama_configured":bool(OLLAMA_BASE_URL and OLLAMA_API_KEY),"ollama_reachable":ollama_reachable,"model":OLLAMA_MODEL}

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
 safe_context={"currency":str(context.get("currency","YER"))[:3],"income":context.get("income",0),"expenses":context.get("expenses",0),"net":context.get("net",0),"transactions":safe}
 system=("أنت WALLET OS، مساعد تحليل مالي. استخدم فقط الأرقام المقدمة ولا تخترع بيانات. وضح العملة والفترة وحدود البيانات. التحويلات ليست دخلا ولا مصروفا. لا تنفذ معاملات أو تدّع تنفيذها. قدم توصيات عملية غير مضمونة النتائج. أجب باللغة العربية." if req.language=="ar" else "You are WALLET OS, a careful personal finance analysis assistant. Use only supplied facts, state currency and limitations, never invent data or claim to execute transactions.")
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(180,connect=10)) as c:
   r=await c.post(OLLAMA_BASE_URL+"/api/chat",headers={"Authorization":"Bearer "+OLLAMA_API_KEY,"Content-Type":"application/json"},json={"model":OLLAMA_MODEL,"stream":False,"messages":[{"role":"system","content":system+"\nFinancial data (sanitized): "+__import__("json").dumps(safe_context,ensure_ascii=False)},{"role":"user","content":req.message}]})
  if r.status_code>=400: raise HTTPException(502,"فشل نموذج Ollama في معالجة الطلب.")
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
