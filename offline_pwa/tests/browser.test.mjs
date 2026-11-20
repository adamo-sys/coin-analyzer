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

// Catch wrong ordering/roles, leaked URLs, stale async selection and accidental writes.
async function viewerSnapshot(p) {
  return p.evaluate(async()=>{
    const db=await (await import('./storage.js')).openStore();
    try {const data=await db.list();return {...data,photos:await Promise.all(data.photos.map(async photo=>({...photo,blob:[...new Uint8Array(await photo.blob.arrayBuffer())]})))};}
    finally {db.close();}
  });
}
async function viewerFixtures(p) {
  await draft(p,'Multi');
  await p.evaluate(async()=>{
    const db=await (await import('./storage.js')).openStore();
    try {
      const data=await db.list(),entry=data.entries[0];
      const canvas=document.createElement('canvas');canvas.width=7;canvas.height=3;
      canvas.getContext('2d').fillRect(0,0,7,3);
      const blob=await new Promise(ok=>canvas.toBlob(ok));
      const photo=await (await import('./media.js')).normalizePhoto(blob,'reverse');
      await db.commit({id:entry.id,expectedRevision:1,label:'Multi',photos:[photo]});
      await db.commit({id:crypto.randomUUID(),expectedRevision:0,label:'Empty'});
    } finally {db.close();}
  });
  await p.reload();await p.locator('#entries li').filter({hasText:'Empty'}).waitFor();
}
const review=(p,label)=>p.locator('#entries li').filter({hasText:label}).getByRole('button').click();
async function photoVisible(p,width) {
  await p.waitForFunction(width=>{
    const img=document.getElementById('retained-photo');
    return img && !img.hidden && img.complete && img.naturalWidth===width;
  },width);
}
async function trackViewerUrls(p) {
  await p.evaluate(()=>{
    const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
    window.viewerUrls=new Set();
    URL.createObjectURL=blob=>{const url=create(blob);viewerUrls.add(url);return url;};
    URL.revokeObjectURL=url=>{viewerUrls.delete(url);revoke(url);};
  });
}

// Observe listener lifetime and cancellation without depending on mobile prompt UI.
async function protectedPage(ctx) {
  await ctx.addInitScript(()=>{
    const add=window.addEventListener,remove=window.removeEventListener,listeners=new Set();
    window.addEventListener=function(type,handler,...args){if(type==='beforeunload')listeners.add(handler);return add.call(this,type,handler,...args);};
    window.removeEventListener=function(type,handler,...args){if(type==='beforeunload')listeners.delete(handler);return remove.call(this,type,handler,...args);};
    window.departureState=()=>{
      const event=new Event('beforeunload',{cancelable:true});
      window.dispatchEvent(event);
      return {listeners:listeners.size,prevented:event.defaultPrevented};
    };
  });
  return page(ctx);
}
async function protection(p,expected) {
  assert.deepEqual(await p.evaluate(()=>departureState()),{listeners:expected?1:0,prevented:expected});
}
async function selectPhoto(p) {
  const bytes=await p.evaluate(async()=>{
    const c=document.createElement('canvas');c.width=3;c.height=2;
    const blob=await new Promise(ok=>c.toBlob(ok,'image/png'));
    return [...new Uint8Array(await blob.arrayBuffer())];
  });
  await p.locator('#photos').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:Buffer.from(bytes)});
}
async function formSnapshot(p) {
  return p.evaluate(()=>({label:document.getElementById('label').value,role:document.getElementById('role').value,
    files:[...document.getElementById('photos').files].map(f=>({name:f.name,size:f.size,lastModified:f.lastModified})),
    src:document.getElementById('retained-photo').getAttribute('src'),status:document.getElementById('photo-status').textContent}));
}

test('unsaved protection follows normalized labels and selected photos, not role or viewing',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await protection(p,false);
    await viewerFixtures(p);await review(p,'Multi');await photoVisible(p,4);await protection(p,false);
    await p.locator('#photo-next').click();await photoVisible(p,7);await protection(p,false);
    await p.locator('#role').selectOption('reverse');await protection(p,false);
    await p.locator('#label').fill('Changed');await protection(p,true);
    await p.locator('#label').fill('  Multi  ');await protection(p,false);
    await selectPhoto(p);await protection(p,true);
    await p.locator('#photos').setInputFiles([]);await protection(p,false);
    await p.locator('#new').click();await protection(p,false);
    await p.locator('#label').fill('   ');await protection(p,false);
  } finally {await ctx.close();}
});

test('discard guard preserves complete form and viewer on cancellation and accepts navigation',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await viewerFixtures(p);await review(p,'Multi');await photoVisible(p,4);
    const evidence=await viewerSnapshot(p);
    await p.locator('#label').fill('Unretained');await selectPhoto(p);await p.locator('#role').selectOption('detail');
    const before=await formSnapshot(p);
    p.once('dialog',d=>d.dismiss());await review(p,'Empty');
    assert.deepEqual(await formSnapshot(p),before);await protection(p,true);
    p.once('dialog',d=>d.dismiss());await p.locator('#new').click();
    assert.deepEqual(await formSnapshot(p),before);await protection(p,true);
    p.once('dialog',d=>d.accept());await review(p,'Empty');
    assert.equal(await p.locator('#label').inputValue(),'Empty');
    assert.equal(await p.locator('#photos').evaluate(e=>e.files.length),0);await protection(p,false);
    await p.locator('#label').fill('Discard me');
    p.once('dialog',d=>d.accept());await p.locator('#new').click();
    assert.equal(await p.locator('#label').inputValue(),'');await protection(p,false);
    assert.deepEqual(await viewerSnapshot(p),evidence);
  } finally {await ctx.close();}
});

test('acknowledged retain resets normalized baseline and clears selected-photo protection',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await p.locator('#label').fill('  Saved label  ');await selectPhoto(p);
    await protection(p,true);await p.locator('#retain').click();
    await p.locator('#write-status').filter({hasText:'Retained on this phone'}).waitFor();await protection(p,false);
    assert.equal(await p.locator('#photos').evaluate(e=>e.files.length),0);
    await p.locator('#label').fill('Changed');await protection(p,true);
    await p.locator('#label').fill('Saved label');await protection(p,false);
    const data=await viewerSnapshot(p);assert.equal(data.entries[0].label,'Saved label');assert.equal(data.photos.length,1);
    await p.reload();await review(p,'Saved label');await photoVisible(p,3);await protection(p,false);
  } finally {await ctx.close();}
});

test('failed UI write retains edits and departure protection without changing evidence',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await viewerFixtures(p);await review(p,'Multi');await photoVisible(p,4);
    const before=await viewerSnapshot(p);await p.locator('#label').fill('Failed edit');await selectPhoto(p);
    await p.evaluate(()=>{
      const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(...args){if(this.name==='photos')throw new DOMException('synthetic quota','QuotaExceededError');return put.apply(this,args);};
    });
    await p.locator('#retain').click();await p.locator('#write-status').filter({hasText:/quota exhausted/}).waitFor();
    await protection(p,true);assert.equal(await p.locator('#label').inputValue(),'Failed edit');
    assert.equal(await p.locator('#photos').evaluate(e=>e.files.length),1);
    assert.deepEqual(await viewerSnapshot(p),before);
  } finally {await ctx.close();}
});

test('uncertain UI write preserves recovery guidance and protection until explicit discard',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await viewerFixtures(p);await review(p,'Multi');await photoVisible(p,4);
    await p.locator('#label').fill('Uncertain');
    await p.evaluate(()=>{
      const native=IDBDatabase.prototype.transaction;let written=false;
      window.restoreTransactions=()=>{IDBDatabase.prototype.transaction=native;};
      IDBDatabase.prototype.transaction=function(...args){
        if(written && args[1]==='readonly')throw new DOMException('synthetic readback failure','UnknownError');
        const tx=native.apply(this,args);if(args[1]==='readwrite')tx.addEventListener('complete',()=>{written=true;});return tx;
      };
    });
    await p.locator('#retain').click();
    await p.locator('#write-status').filter({hasText:/may have committed.*readback failed/}).waitFor();await protection(p,true);
    await p.evaluate(()=>restoreTransactions());
    await p.locator('#label').fill('Multi');await protection(p,true);
    assert.match(await p.locator('#write-status').innerText(),/may have committed.*readback failed/);
    await p.locator('#prepare').click();assert.match(await p.locator('#shell-status').innerText(),/deferred/);
    const data=await viewerSnapshot(p);assert.equal(data.entries.length,2);assert.ok(data.entries.some(e=>e.label==='Uncertain'));
    await p.locator('#retain').click();
    await p.locator('#write-status').filter({hasText:/Connection closed or recovery required/}).waitFor();
    await protection(p,true);
    p.once('dialog',d=>d.dismiss());await p.locator('#new').click();await protection(p,true);
    p.once('dialog',d=>d.accept());await p.locator('#new').click();await protection(p,false);
    assert.deepEqual(await viewerSnapshot(p),data);
  } finally {await ctx.close();}
});

test('active write protects an unchanged form and blocks conflicting internal navigation',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await viewerFixtures(p);await review(p,'Multi');await photoVisible(p,4);
    await protection(p,false);
    await p.evaluate(()=>{
      const digest=crypto.subtle.digest.bind(crypto.subtle);
      window.releaseWrite=undefined;let held=false;
      crypto.subtle.digest=async(...args)=>{
        if(!held){held=true;await new Promise(ok=>{window.releaseWrite=ok;});}
        return digest(...args);
      };
    });
    await p.locator('#retain').click();await p.waitForFunction(()=>typeof releaseWrite==='function');await protection(p,true);
    const before=await formSnapshot(p);
    await review(p,'Empty');
    // New is disabled, but its handler must also reject conflicting navigation.
    await p.evaluate(()=>document.getElementById('new').onclick());
    assert.deepEqual(await formSnapshot(p),before);
    await p.locator('#prepare').click();assert.match(await p.locator('#shell-status').innerText(),/deferred/);
    await p.evaluate(()=>releaseWrite());
    await p.locator('#write-status').filter({hasText:'Retained on this phone'}).waitFor();await protection(p,false);
  } finally {await ctx.close();}
});

test('offline foreground reopen preserves unsaved form and exact retained evidence',async()=>{
  const ctx=await context();try {
    const p=await protectedPage(ctx);await viewerFixtures(p);await install(p);await review(p,'Multi');await photoVisible(p,4);
    const evidence=await viewerSnapshot(p);await ctx.clearCookies();await ctx.setOffline(true);requests=[];
    await p.locator('#label').fill('Offline edit');await selectPhoto(p);await p.locator('#role').selectOption('obverse');
    await p.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
    await photoVisible(p,4);await protection(p,true);
    assert.equal(await p.locator('#label').inputValue(),'Offline edit');
    assert.equal(await p.locator('#photos').evaluate(e=>e.files.length),1);
    assert.equal(await p.locator('#role').inputValue(),'obverse');
    assert.deepEqual(await viewerSnapshot(p),evidence);assert.deepEqual(requests,[]);
    p.once('dialog',d=>d.accept());await p.locator('#new').click();await protection(p,false);
    await p.reload();await review(p,'Multi');await photoVisible(p,4);
    assert.deepEqual(await viewerSnapshot(p),evidence);assert.deepEqual(requests,[]);
  } finally {await ctx.close();}
});
test('retained viewer navigates in reference order, releases URLs and preserves exact data',async()=>{
  const ctx=await context();try {
    const p=await page(ctx);await viewerFixtures(p);const before=await viewerSnapshot(p);
    await trackViewerUrls(p);await review(p,'Multi');await photoVisible(p,4);
    assert.match(await p.locator('#photo-status').innerText(),/1 of 2.*unassigned/i);
    assert.equal(await p.locator('#photo-previous').isDisabled(),true);
    const first=await p.locator('#retained-photo').getAttribute('src');
    await p.locator('#photo-next').click();await photoVisible(p,7);
    assert.match(await p.locator('#photo-status').innerText(),/2 of 2.*reverse/i);
    assert.equal(await p.locator('#photo-next').isDisabled(),true);
    assert.equal(await p.evaluate(url=>viewerUrls.has(url),first),false);
    await p.locator('#photo-previous').click();await photoVisible(p,4);
    await review(p,'Empty');
    await p.locator('#photo-status').filter({hasText:/no retained photos/i}).waitFor({timeout:5000});
    assert.match(await p.locator('#photo-status').innerText(),/no retained photos/i);
    assert.equal(await p.locator('#retained-photo').getAttribute('src'),null);
    assert.equal(await p.locator('#photo-next').isDisabled(),true);
    assert.equal(await p.locator('#photo-previous').isDisabled(),true);
    assert.equal(await p.evaluate(()=>viewerUrls.size),0);
    await review(p,'Multi');await photoVisible(p,4);
    await p.locator('#label').fill('Uncommitted');
    p.once('dialog',d=>d.dismiss());await review(p,'Empty');await photoVisible(p,4);
    p.once('dialog',d=>d.dismiss());await p.locator('#new').click();await photoVisible(p,4);
    assert.equal(await p.locator('#label').inputValue(),'Uncommitted');
    p.once('dialog',d=>d.accept());await p.locator('#new').click();
    assert.equal(await p.evaluate(()=>viewerUrls.size),0);
    assert.equal(await p.locator('#retained-photo').getAttribute('src'),null);
    await review(p,'Multi');await photoVisible(p,4);
    await p.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
    await photoVisible(p,4);assert.equal(await p.evaluate(()=>viewerUrls.size),1);
    assert.deepEqual(await viewerSnapshot(p),before);
  } finally {await ctx.close();}
});
test('retained viewer reopens multiple photos offline without a session or writes',async()=>{
  const ctx=await context();try {
    const p=await page(ctx);await viewerFixtures(p);await install(p);
    const before=await viewerSnapshot(p);await p.close();
    await ctx.clearCookies();await ctx.setOffline(true);requests=[];
    const cold=await page(ctx);await review(cold,'Multi');await photoVisible(cold,4);
    await cold.locator('#photo-next').click();await photoVisible(cold,7);
    assert.deepEqual(await viewerSnapshot(cold),before);assert.deepEqual(requests,[]);
  } finally {await ctx.close();}
});
test('delayed draft selection cannot replace a newer selection or New mode',async()=>{
  const ctx=await context();try {
    const p=await page(ctx);await viewerFixtures(p);await trackViewerUrls(p);
    // Hold the real validated read at its hash boundary, keeping IDB reads real.
    await p.evaluate(()=>{
      const digest=crypto.subtle.digest.bind(crypto.subtle);
      window.heldReads=[];window.finishedViewerReads=0;
      crypto.subtle.digest=async(...args)=>{
        if(window.holdViewerReads)await new Promise(ok=>heldReads.push(ok));
        const result=await digest(...args);++window.finishedViewerReads;return result;
      };
      window.holdViewerReads=true;
    });
    await review(p,'Multi');await p.waitForFunction(()=>heldReads.length===1);
    await p.evaluate(()=>{window.holdViewerReads=false;});
    await review(p,'Empty');
    await p.locator('#photo-status').filter({hasText:/no retained photos/i}).waitFor();
    await p.evaluate(()=>heldReads.splice(0).forEach(ok=>ok()));
    await p.waitForFunction(()=>finishedViewerReads>=4);
    await p.evaluate(()=>new Promise(requestAnimationFrame));
    assert.equal(await p.locator('#retained-photo').getAttribute('src'),null);
    assert.match(await p.locator('#photo-status').innerText(),/no retained photos/i);
    assert.equal(await p.evaluate(()=>viewerUrls.size),0);
    await p.evaluate(()=>{window.holdViewerReads=true;window.finishedViewerReads=0;});await review(p,'Multi');
    await p.waitForFunction(()=>heldReads.length===1);await p.locator('#new').click();
    await p.evaluate(()=>{window.holdViewerReads=false;heldReads.splice(0).forEach(ok=>ok());});
    await p.waitForFunction(()=>finishedViewerReads===2);
    await p.evaluate(()=>new Promise(requestAnimationFrame));
    assert.equal(await p.locator('#retained-photo').getAttribute('src'),null);
    assert.equal(await p.evaluate(()=>viewerUrls.size),0);
  } finally {await ctx.close();}
});

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

// Faults run against real IDB transactions. Removing cancellation, precommit
// validation, or the async-validation lifetime guard must fail these cases.
async function migrationScenario(p, fault) {
  return p.evaluate(async fault => {
    const {openStore}=await import('./storage.js');
    const {normalizePhoto}=await import('./media.js');
    const canvas=document.createElement('canvas');canvas.width=4;canvas.height=4;
    const blob=await new Promise(ok=>canvas.toBlob(ok,'image/png'));
    const entries=Array.from({length:10},(_,i)=>({id:crypto.randomUUID(),revision:1,label:`Legacy ${i}`,photoIds:[]}));
    const photo={...await normalizePhoto(blob,'unassigned'),entryId:entries[0].id};
    entries[0].photoIds=[photo.id];
    const photos=[photo];
    if(fault==='missing-reference')photos.length=0;
    if(fault==='wrong-owner')photo.entryId=entries[1].id;
    if(fault==='orphan')entries[0].photoIds=[];
    if(fault==='corrupt-size')photo.size++;
    if(fault==='corrupt-hash')photo.sha256='0'.repeat(64);
    if(fault==='duplicate-reference')entries[1].photoIds=[photo.id];
    if(fault==='invalid-revision')entries[0].revision=0;
    const name='atomic-migration';
    await new Promise((ok,no)=>{
      const r=indexedDB.open(name,1);
      r.onupgradeneeded=()=>{
        const e=r.result.createObjectStore('entries',{keyPath:'id'}),m=r.result.createObjectStore('photos',{keyPath:'id'});
        for(const v of entries)e.put(v);for(const v of photos)m.put(v);
      };
      r.onsuccess=()=>{r.result.close();ok();};r.onerror=()=>no(r.error);
    });
    async function snapshot() {
      const d=await new Promise((ok,no)=>{const r=indexedDB.open(name);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
      const t=d.transaction(['entries','photos']),get=s=>new Promise((ok,no)=>{const r=t.objectStore(s).getAll();r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
      // Request success precedes transaction completion; close must not race the next upgrade.
      const done=new Promise((ok,no)=>{t.oncomplete=ok;t.onabort=()=>no(t.error || new Error('Snapshot transaction aborted'));});
      const [entries,photos]=await Promise.all([get('entries'),get('photos'),done]);
      const result={version:d.version,stores:[...d.objectStoreNames],entries,photos:await Promise.all(photos.map(async p=>({...p,blob:[...new Uint8Array(await p.blob.arrayBuffer())]})))};
      d.close();return result;
    }
    const before=await snapshot();
    const nativeTimeout=window.setTimeout,nativeOpen=IDBFactory.prototype.open;
    const nativePut=IDBObjectStore.prototype.put,nativeUpdate=IDBCursor.prototype.update;
    const nativeDigest=crypto.subtle.digest;
    let deadline,triggered=false,upgrade,delayed=false,completed=false;
    window.setTimeout=(fn,ms,...args)=>{if(ms===5000)deadline=fn;return nativeTimeout(fn,ms,...args);};
    IDBFactory.prototype.open=function(...args){
      const r=nativeOpen.apply(this,args);
      if(args[0]===name && args[1]===2)r.addEventListener('upgradeneeded',()=>{
        upgrade=r.transaction;
        // A queued deadline may run after native commit but before open success.
        upgrade.addEventListener('complete',()=>{completed=true;if(fault==='completed-deadline'){triggered=true;deadline();}});
      });
      return r;
    };
    function afterWrite() {
      if(triggered || !['timeout-after-write','interrupt'].includes(fault))return;
      triggered=true;
      if(fault==='interrupt')upgrade.abort();else deadline();
    }
    IDBObjectStore.prototype.put=function(...args){const r=nativePut.apply(this,args);if(this.name==='entries' && this.transaction===upgrade)afterWrite();return r;};
    IDBCursor.prototype.update=function(...args){const r=nativeUpdate.apply(this,args);if(this.source.name==='entries' && this.source.transaction===upgrade)afterWrite();return r;};
    crypto.subtle.digest=async function(...args){
      if(fault==='page-close') {
        window.migrationBefore=before;window.migrationHeld=true;
        await new Promise(()=>{}); // Page termination must abort this upgrade.
      }
      if(!delayed && ['delayed-validation','timeout-during-validation'].includes(fault)) {
        delayed=true;
        // Cross several event-loop tasks while IDB would otherwise auto-commit.
        for(let i=0;i<3;i++)await new Promise(ok=>nativeTimeout(ok,0));
        if(fault==='timeout-during-validation'){triggered=true;deadline();}
      }
      return nativeDigest.apply(this,args);
    };
    let code;
    try {const d=await openStore(name);d.close();}
    catch(e){code=e.code;}
    finally {
      window.setTimeout=nativeTimeout;IDBFactory.prototype.open=nativeOpen;
      IDBObjectStore.prototype.put=nativePut;IDBCursor.prototype.update=nativeUpdate;
      crypto.subtle.digest=nativeDigest;
    }
    // Queued behind the original open: this snapshot also detects a late commit.
    const after=await snapshot();
    let recovered;
    if(['timeout-after-write','timeout-during-validation','interrupt'].includes(fault)) {
      const d=await openStore(name);const data=await d.list();d.close();
      recovered={entries:data.entries,hash:data.photos[0].sha256};
    }
    return {code,before,after,recovered,triggered,delayed,completed};
  },fault);
}

test('closing the page during migration preserves v1 evidence and permits recovery', async()=>{
  const ctx=await context();try {
    const p=await page(ctx);
    const interrupted=migrationScenario(p,'page-close').then(()=>false,()=>p.isClosed());
    await p.waitForFunction(()=>window.migrationHeld);
    const before=await p.evaluate(()=>window.migrationBefore);
    await p.close();assert.equal(await interrupted,true);
    const next=await page(ctx);
    const result=await next.evaluate(async()=>{
      const d=await new Promise((ok,no)=>{const r=indexedDB.open('atomic-migration');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
      const t=d.transaction(['entries','photos']),get=s=>new Promise(ok=>{const r=t.objectStore(s).getAll();r.onsuccess=()=>ok(r.result);});
      const [entries,photos]=await Promise.all([get('entries'),get('photos')]);
      const before={version:d.version,stores:[...d.objectStoreNames],entries,photos:await Promise.all(photos.map(async p=>({...p,blob:[...new Uint8Array(await p.blob.arrayBuffer())]})))};
      d.close();const recovered=await (await import('./storage.js')).openStore('atomic-migration');
      const data=await recovered.list();recovered.close();return {before,entries:data.entries,hash:data.photos[0].sha256};
    });
    assert.deepEqual(result.before,before);
    assert.deepEqual(result.entries,before.entries.map(e=>({...e,state:'draft'})));
    assert.equal(result.hash,before.photos[0].sha256);
  }finally{await ctx.close();}
});

for(const fault of ['missing-reference','wrong-owner','orphan','corrupt-size','corrupt-hash','duplicate-reference','invalid-revision']) {
  test(`v1 ${fault} rejects before commit and preserves exact legacy evidence`, async()=>{
    const ctx=await context();try {
      const result=await migrationScenario(await page(ctx),fault);
      assert.equal(result.code,'recovery-required');
      assert.deepEqual(result.after,result.before);
      assert.equal(result.completed,false);
    }finally{await ctx.close();}
  });
}

for(const fault of ['timeout-after-write','timeout-during-validation','interrupt']) {
  test(`v1 ${fault} aborts schema and partial writes; a clean retry recovers`, async()=>{
    const ctx=await context();try {
      const result=await migrationScenario(await page(ctx),fault);
      assert.equal(result.triggered,true);
      assert.equal(result.code,fault==='interrupt'?'recovery-required':'blocked');
      assert.deepEqual(result.after,result.before);
      assert.equal(result.completed,false);
      assert.deepEqual(result.recovered.entries,result.before.entries.map(e=>({...e,state:'draft'})));
      assert.equal(result.recovered.hash,result.before.photos[0].sha256);
    }finally{await ctx.close();}
  });
}

for(const fault of ['delayed-validation','completed-deadline']) {
  test(`v1 ${fault} acknowledges only a valid completed migration`, async()=>{
    const ctx=await context();try {
      const result=await migrationScenario(await page(ctx),fault);
      assert.equal(result.code,undefined);
      assert.equal(result[fault==='delayed-validation'?'delayed':'triggered'],true);
      assert.equal(result.completed,true);
      assert.equal(result.after.version,2);
      assert.deepEqual(result.after.entries,result.before.entries.map(e=>({...e,state:'draft'})));
      assert.deepEqual(result.after.photos,result.before.photos);
    }finally{await ctx.close();}
  });
}

test('post-commit readback failure reports uncertainty; reopen finds the committed draft', async()=>{
  const ctx=await context();try {
    const p=await page(ctx);
    const result=await p.evaluate(async()=>{
      const {openStore}=await import('./storage.js');const d=await openStore();
      const native=IDBDatabase.prototype.transaction;let written=false,code,guard;
      IDBDatabase.prototype.transaction=function(...args){
        if(written && args[1]==='readonly')throw new DOMException('synthetic readback failure','UnknownError');
        const t=native.apply(this,args);if(args[1]==='readwrite')t.addEventListener('complete',()=>{written=true;});return t;
      };
      const id=crypto.randomUUID();
      try{await d.commit({id,expectedRevision:0,label:'Uncertain draft'});}catch(e){code=e.code;}
      finally{IDBDatabase.prototype.transaction=native;}
      try{await d.commit({id,expectedRevision:0,label:'Unsafe retry'});}catch(e){guard=e.code;}
      d.close();const reopened=await openStore();const data=await reopened.list();reopened.close();
      return {code,guard,entries:data.entries,id};
    });
    assert.equal(result.code,'outcome-uncertain');assert.equal(result.guard,'recovery-required');
    assert.deepEqual(result.entries,[{id:result.id,revision:1,label:'Uncertain draft',state:'draft',photoIds:[]}]);
  }finally{await ctx.close();}
});
