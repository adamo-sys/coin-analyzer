/* Build replaces this value with a closed, content-addressed shell inventory. */
const SHELL = __SHELL_MANIFEST__;
const BASE = new URL('./', self.location.href);
const CACHE = `coin-show-shell-${SHELL.version}`;
const urls = new Map(SHELL.assets.map(a => [new URL(a.path, BASE).href, a]));
const marker = new URL('__complete__', BASE).href;
const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2,'0')).join('');

async function complete(cache) {
  if ((await cache.match(marker))?.status !== 200) return false;
  for (const [url,asset] of urls) {
    const response=await cache.match(url);
    if (!response || await digest(await response.arrayBuffer())!==asset.sha256) return false;
  }
  return true;
}

self.addEventListener('install', event => event.waitUntil((async () => {
  // Never disturb an existing complete cache, including a reinstall of this version.
  if ((await caches.keys()).includes(CACHE) && await complete(await caches.open(CACHE))) return;
  // Keep at most current + prior compatible + one candidate; never evict on install.
  if ((await caches.keys()).filter(k=>k.startsWith('coin-show-shell-')).length>=3) throw new Error('Shell cache limit; compatible startup required before another update');
  const stageName=`${CACHE}-staging`;
  const stage=await caches.open(stageName);
  let published=false;
  try {
    for (const [url, asset] of urls) {
      const response=await fetch(url,{credentials:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(8000)});
      if (response.status!==200 || response.redirected || response.type==='opaque' ||
          response.headers.get('Content-Type')?.split(';')[0].trim()!==asset.type) throw new Error('Shell response rejected');
      const bytes=await response.clone().arrayBuffer();
      if (bytes.byteLength>3*1024*1024 || await digest(bytes)!==asset.sha256) throw new Error('Shell integrity rejected');
      await stage.put(url,response);
    }
    const target=await caches.open(CACHE);
    for (const [url] of urls) await target.put(url,await stage.match(url));
    await target.put(marker,new Response(SHELL.version));
    if (!await complete(target)) throw new Error('Incomplete shell');
    published=true;
  } finally {
    await caches.delete(stageName);
    if (!published) await caches.delete(CACHE);
  }
})()));

self.addEventListener('activate', event => event.waitUntil((async () => {
  // No skipWaiting, reload, old-cache deletion, or automatic database migration.
  if (self.registration.navigationPreload) await self.registration.navigationPreload.disable();
})()));

self.addEventListener('fetch', event => {
  const request=event.request, url=new URL(request.url);
  if (request.method!=='GET' || url.origin!==BASE.origin || url.search) return;
  const relative=url.pathname.slice(BASE.pathname.length);
  const navigation=request.mode==='navigate' && url.pathname.startsWith(BASE.pathname) &&
    (relative==='' || relative==='index.html' || /^entry\/[0-9a-f-]{36}$/.test(relative));
  const target=navigation ? new URL('index.html',BASE).href : url.href;
  if (!navigation && !urls.has(target)) return; // Auth/API/unknown paths always pass through.
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    const response=await cache.match(target);
    return response || new Response('Local shell unavailable. Re-provision at home; local data has not been reset.',{status:503,headers:{'Content-Type':'text/plain'}});
  })());
});

self.addEventListener('message', event => {
  if(event.data?.type==='ACCEPT_LOCAL_SCHEMA' && event.data.version===2) {
    event.waitUntil((async()=>{
      if(!await complete(await caches.open(CACHE)))return;
      const old=(await caches.keys()).filter(k=>k.startsWith('coin-show-shell-') && k!==CACHE);
      // Application sends this only after opening and validating the local database.
      // Keep the most recent previous shell, never touch IndexedDB.
      for(const key of old.slice(0,-1))await caches.delete(key);
    })());
    return;
  }
  if (event.data?.type!=='CHECK_SHELL' || !event.ports[0]) return;
  event.waitUntil((async()=>{
    try { event.ports[0].postMessage({complete:await complete(await caches.open(CACHE))}); }
    catch { event.ports[0].postMessage({complete:false}); }
  })());
});
