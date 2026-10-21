// Removing transactional commit, hash verification, or local-only routing must fail these tests.
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium } from 'playwright';

let browser, server, directory, origin, files;
let denial = false, broken = '', corrupt = false, requests = [];
const prefix = '/offline-coin-show/';
const types = { html: 'text/html', js: 'text/javascript', css: 'text/css', png: 'image/png', webmanifest: 'application/manifest+json', json: 'application/json' };
before(async () => {
  directory = await mkdtemp(join(tmpdir(), 'coin-pwa-test-'));
  const build = join(directory, 'build');
  execFileSync(process.env.PWA_PYTHON || 'python', ['../tools/build_offline_pwa.py', build]);
  const inventory = JSON.parse(await readFile(join(build, 'shell.json')));
  files = new Map(await Promise.all([...inventory.assets.map(a => a.path), 'sw.js', 'shell.json'].map(async p => [p, await readFile(join(build, p))])));
  server = createServer((req, res) => {
    requests.push(req.url);
    // Synthetic server boundary, not a pairing/session implementation.
    if (denial || req.headers.cookie !== 'fixture=approved') { res.writeHead(401, {'Cache-Control':'no-store'}); res.end('denied'); return; }
    let path = req.url.slice(prefix.length);
    if (!path || path.startsWith('entry/')) path = 'index.html';
    if (!req.url.startsWith(prefix) || !files.has(path)) { res.writeHead(404); res.end(); return; }
    if (broken === path) { res.writeHead(200, {'Content-Type':corrupt?types[path.split('.').at(-1)]:'text/html','Cache-Control':'no-store'}); res.end(corrupt?'corrupted bytes':'<html>login</html>'); return; }
    res.writeHead(200, {'Content-Type':types[path.split('.').at(-1)],'Cache-Control':'no-store'});
    res.end(files.get(path));
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch(process.env.PWA_BROWSER_CHANNEL ? {channel:process.env.PWA_BROWSER_CHANNEL} : {});
});
after(async () => { await browser?.close(); await new Promise(r => server?.close(r)); if(directory) await rm(directory,{recursive:true}); });

async function context() {
  denial=false; broken=''; corrupt=false; requests=[];
  const ctx = await browser.newContext();
  await ctx.addCookies([{name:'fixture',value:'approved',url:origin}]);
  return ctx;
}
async function page(ctx) {
  const p = await ctx.newPage(); await p.goto(origin+prefix);
  await p.locator('#status').filter({hasText:'Local workspace'}).waitFor();
  return p;
}
async function install(p) {
  await p.locator('#prepare').click();
  await p.locator('#shell-status').filter({hasText:/prepared|failed/}).waitFor();
  await p.waitForFunction(async () => (await navigator.serviceWorker.getRegistration())?.active);
  await p.reload(); await p.waitForFunction(() => navigator.serviceWorker.controller);
}
async function draft(p, label='Synthetic coin') {
  return p.evaluate(async label => {
    const {openStore} = await import('./storage.js');
    const {normalizePhoto} = await import('./media.js');
    const canvas=document.createElement('canvas'); canvas.width=4; canvas.height=4;
    canvas.getContext('2d').fillRect(0,0,4,4);
    const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));
    const photo=await normalizePhoto(blob,'unassigned');
    const db=await openStore();
    try { return await db.commit({id:crypto.randomUUID(),expectedRevision:0,label,photos:[photo]}); }
    finally { db.close(); }
  },label);
}

test('cached cold deep-link starts without network or session; committed photos survive', async () => {
  const ctx=await context(); try {
    const p=await page(ctx); await install(p); const entry=await draft(p); await p.close();
    await ctx.clearCookies(); await ctx.setOffline(true); requests=[];
    const cold=await ctx.newPage(); await cold.goto(origin+prefix+'entry/'+entry.id);
    await cold.locator('#entries').filter({hasText:'Synthetic coin'}).waitFor();
    const data=await cold.evaluate(async()=> { const db=await (await import('/offline-coin-show/storage.js')).openStore(); try{const d=await db.list();return {entries:d.entries,photos:d.photos.map(p=>({size:p.blob.size,sha256:p.sha256}))};}finally{db.close();} });
    assert.equal(data.entries[0].id,entry.id); assert.equal(data.photos[0].size>0,true);
    assert.equal(data.photos[0].sha256.length,64); assert.deepEqual(requests,[]);
  } finally { await ctx.close(); }
});

test('explicit form acknowledges retained data only after a committed reopen', async () => {
  const ctx=await context(); try {
    const p=await page(ctx); await p.locator('#label').fill('Form entry');
    await p.locator('#retain').click(); await p.locator('#write-status').filter({hasText:'Retained on this phone'}).waitFor();
    await p.reload(); await p.locator('#entries').filter({hasText:'Form entry'}).waitFor();
    assert.match(await p.locator('#readiness').innerText(),/acceptance pending/i);
  } finally { await ctx.close(); }
});

test('v1 migration preserves IDs and blob hashes; future schema is never reset', async () => {
  const ctx=await context(); try {
    const p=await page(ctx); const entry=await draft(p);
    const result=await p.evaluate(async id=> {
      const mod=await import('./storage.js');
      // Copy current public records into the documented version-1 fixture database.
      let db=await mod.openStore(); const before=await db.list(); db.close();
      await new Promise((ok,no)=>{ const r=indexedDB.open('migration-fixture',1); r.onupgradeneeded=()=>{r.result.createObjectStore('entries',{keyPath:'id'});r.result.createObjectStore('photos',{keyPath:'id'});};r.onsuccess=()=>{const d=r.result;const t=d.transaction(['entries','photos'],'readwrite');for(const e of before.entries){const v={...e};delete v.state;t.objectStore('entries').put(v);}for(const f of before.photos)t.objectStore('photos').put(f);t.oncomplete=()=>{d.close();ok();};};r.onerror=()=>no(r.error);});
      db=await mod.openStore('migration-fixture'); const after=await db.list(); db.close();
      await new Promise(ok=>{const r=indexedDB.open('future-fixture',99);r.onupgradeneeded=()=>r.result.createObjectStore('untouched');r.onsuccess=()=>{r.result.close();ok();};});
      let code;try{await mod.openStore('future-fixture');}catch(e){code=e.code;}
      return {same:after.entries[0].id===id,hash:after.photos[0].sha256,oldHash:before.photos[0].sha256,state:after.entries[0].state,code};
    },entry.id);
    assert.equal(result.same,true); assert.equal(result.hash,result.oldHash); assert.equal(result.state,'draft'); assert.equal(result.code,'newer-schema');
  } finally { await ctx.close(); }
});

test('stale concurrent revision and quota abort preserve previous records and photos', async () => {
  const ctx=await context(); try {
    const p=await page(ctx); const entry=await draft(p);
    const result=await p.evaluate(async id=>{
      const {openStore}=await import('./storage.js');const a=await openStore(),b=await openStore();
      const results=await Promise.allSettled([a.commit({id,expectedRevision:1,label:'First',photos:[]}),b.commit({id,expectedRevision:1,label:'Second',photos:[]})]);
      const before=await a.list();
      const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(value,...args){if(this.name==='photos')throw new DOMException('synthetic quota','QuotaExceededError');return put.call(this,value,...args);};
      let code;try{await a.commit({id,expectedRevision:2,label:'Must roll back',photos:[{...before.photos[0],id:crypto.randomUUID()}]});}catch(e){code=e.code;}finally{IDBObjectStore.prototype.put=put;}
      const after=await a.list();a.close();b.close();return {statuses:results.map(r=>r.status).sort(),conflict:results.find(r=>r.status==='rejected')?.reason.code,code,before:before.entries,after:after.entries,count:after.photos.length};
    },entry.id);
    assert.deepEqual(result.statuses,['fulfilled','rejected']);assert.equal(result.conflict,'revision-conflict');assert.equal(result.code,'quota');assert.deepEqual(result.after,result.before);assert.equal(result.count,1);
  } finally { await ctx.close(); }
});

test('corrupt references block writes, blocked migration cannot upgrade later', async () => {
  const ctx=await context(); try {
    const p=await page(ctx);const entry=await draft(p);
    const result=await p.evaluate(async id=>{
      const {openStore}=await import('./storage.js');
      await new Promise(ok=>{const r=indexedDB.open('coin-show-local');r.onsuccess=()=>{const d=r.result,t=d.transaction('photos','readwrite');t.objectStore('photos').clear();t.oncomplete=()=>{d.close();ok();};};});
      let corruption;try{await openStore();}catch(e){corruption=e.code;}
      const blocker=await new Promise(ok=>{const r=indexedDB.open('blocked-fixture',1);r.onupgradeneeded=()=>{r.result.createObjectStore('entries',{keyPath:'id'});r.result.createObjectStore('photos',{keyPath:'id'});};r.onsuccess=()=>ok(r.result);});
      let blocked;try{await openStore('blocked-fixture');}catch(e){blocked=e.code;}blocker.close();
      const version=await new Promise(ok=>{const r=indexedDB.open('blocked-fixture');r.onsuccess=()=>{const v=r.result.version;r.result.close();ok(v);};});
      return {corruption,blocked,version};
    },entry.id);
    assert.equal(result.corruption,'recovery-required');assert.equal(result.blocked,'blocked');assert.equal(result.version,1);
  } finally { await ctx.close(); }
});

test('failed first install publishes no partial shell', async () => {
  const ctx=await context(); try {
    const p=await page(ctx);broken='storage.js';await p.locator('#prepare').click();
    await p.locator('#shell-status').filter({hasText:'failed'}).waitFor();
    assert.deepEqual(await p.evaluate(()=>caches.keys()),[]);
  } finally { await ctx.close(); }
});

test('denied update leaves offline shell and data; auth/API navigation is never a cache fallback', async () => {
  const ctx=await context(); try {
    const p=await page(ctx);await install(p);const entry=await draft(p);denial=true;
    const code=await p.evaluate(async()=> (await fetch('./api/private')).status);assert.equal(code,401);
    const api=await ctx.newPage();await api.goto(origin+prefix+'api/private');assert.equal(await api.locator('body').innerText(),'denied');await api.close();
    await p.locator('#prepare').click(); await p.locator('#shell-status').filter({hasText:'failed'}).waitFor();
    await p.reload();await p.locator('#entries').filter({hasText:'Synthetic coin'}).waitFor();
    const inventory=await p.evaluate(()=>caches.keys());assert.equal(inventory.length,1);
    assert.ok(entry.id);
  } finally { denial=false;await ctx.close(); }
});

test('invalid v1 migration rolls back schema and preserves original evidence', async () => {
  const ctx=await context();try{
    const p=await page(ctx);
    const result=await p.evaluate(async()=>{
      const original={id:crypto.randomUUID(),revision:1,label:'Unknown old state',photoIds:[],state:'pending'};
      await new Promise(ok=>{const r=indexedDB.open('invalid-v1',1);r.onupgradeneeded=()=>{r.result.createObjectStore('entries',{keyPath:'id'}).put(original);r.result.createObjectStore('photos',{keyPath:'id'});};r.onsuccess=()=>{r.result.close();ok();};});
      let code;try{const d=await (await import('./storage.js')).openStore('invalid-v1');d.close();}catch(e){code=e.code;}
      return await new Promise(ok=>{const r=indexedDB.open('invalid-v1');r.onsuccess=()=>{const d=r.result,version=d.version,q=d.transaction('entries').objectStore('entries').get(original.id);q.onsuccess=()=>{d.close();ok({version,entry:q.result,original,code});};};});
    });
    assert.equal(result.code,'recovery-required');assert.equal(result.version,1);assert.deepEqual(result.entry,result.original);
  }finally{await ctx.close();}
});

test('malformed and oversized image headers fail before persistence; photos cap preserves draft', async () => {
  const ctx=await context();try{
    const p=await page(ctx);const entry=await draft(p);
    const result=await p.evaluate(async id=>{
      const {normalizePhoto}=await import('./media.js'),{openStore}=await import('./storage.js');
      let bad,huge;
      try{await normalizePhoto(new Blob(['not an image'],{type:'image/png'}));}catch(e){bad=e.code;}
      const bytes=new Uint8Array(24);bytes.set([137,80,78,71,13,10,26,10]);const v=new DataView(bytes.buffer);v.setUint32(16,9000);v.setUint32(20,9000);
      try{await normalizePhoto(new Blob([bytes],{type:'image/png'}));}catch(e){huge=e.code;}
      const d=await openStore(),before=await d.list();let cap;
      try{await d.commit({id,expectedRevision:1,label:'Too many',photos:Array.from({length:8},()=>({...before.photos[0],id:crypto.randomUUID()}))});}catch(e){cap=e.code;}
      const after=await d.list();d.close();return {bad,huge,cap,before:before.entries,after:after.entries};
    },entry.id);
    assert.equal(result.bad,'unsupported-photo');assert.equal(result.huge,'unsupported-photo');assert.equal(result.cap,'invalid-input');assert.deepEqual(result.after,result.before);
  }finally{await ctx.close();}
});

test('candidate update with wrong hash preserves prior shell and exact photo evidence', async () => {
  const ctx=await context(),original=files.get('sw.js');try{
    const p=await page(ctx);await install(p);const entry=await draft(p);
    const previous=await p.evaluate(()=>caches.keys());
    files.set('sw.js',Buffer.from(original.toString().replace('"version": "','"version": "candidate-')));
    broken='storage.js';corrupt=true;
    await p.locator('#prepare').click();await p.locator('#shell-status').filter({hasText:'failed'}).waitFor();
    assert.deepEqual(await p.evaluate(()=>caches.keys()),previous);
    await ctx.setOffline(true);await p.reload();await p.locator('#entries').filter({hasText:'Synthetic coin'}).waitFor();
    const result=await p.evaluate(async()=>{const d=await (await import('./storage.js')).openStore();try{const v=await d.list();return {id:v.entries[0].id,count:v.photos.length};}finally{d.close();}});
    assert.equal(result.id,entry.id);assert.equal(result.count,1);
  }finally{files.set('sw.js',original);await ctx.close();}
});

test('shell version count is bounded without deleting previous caches during install', async () => {
  const ctx=await context();try{
    const p=await page(ctx);
    await p.evaluate(async()=>{for(let i=0;i<3;i++)await caches.open('coin-show-shell-old-'+i);});
    await p.locator('#prepare').click();await p.locator('#shell-status').filter({hasText:'failed'}).waitFor();
    assert.equal((await p.evaluate(()=>caches.keys())).length,3);
  }finally{await ctx.close();}
});
