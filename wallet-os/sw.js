const CACHE_NAME="wallet-os-shell-v1";
const SHELL=["/","/manifest.webmanifest","/icon-192.png","/icon-512.png","/logo.svg"];
self.addEventListener("install",event=>{
 event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",event=>{
 event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",event=>{
 const request=event.request;
 if(request.method!=="GET")return;
 const url=new URL(request.url);
 if(url.origin!==self.location.origin||url.pathname.startsWith("/api/")||url.pathname==="/config.js")return;
 if(request.mode==="navigate"){
  event.respondWith(fetch(request).then(response=>{
   if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put("/",copy));}
   return response;
  }).catch(()=>caches.match("/")));
  return;
 }
 event.respondWith(caches.match(request).then(cached=>{
  const update=fetch(request).then(response=>{
   if(response&&response.ok)caches.open(CACHE_NAME).then(cache=>cache.put(request,response.clone()));
   return response;
  });
  return cached||update;
 }));
});
