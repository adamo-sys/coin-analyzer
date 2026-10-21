import {openStore} from './storage.js';
import {normalizePhoto} from './media.js';
const el=id=>document.getElementById(id);
let store,current={id:crypto.randomUUID(),revision:0},dirty=false,busy=false;
const connection=()=>{el('connection').textContent=navigator.onLine?'Network available; drafts remain local.':'Offline · drafts use local storage.';};
connection();addEventListener('online',connection);addEventListener('offline',connection);
function error(e) {el('write-status').textContent=e.message || 'Local data unavailable. Preserve this origin and reopen for recovery.';}
function changed(){dirty=true;el('write-status').textContent='Not retained: uncommitted changes.';}
el('label').addEventListener('input',changed);el('photos').addEventListener('change',changed);el('role').addEventListener('change',changed);
async function storageStatus(request=false) {
  try {
    const api=navigator.storage;
    const granted=request?await api?.persist?.():await api?.persisted?.();
    const estimate=await api?.estimate?.();
    el('storage-status').textContent=`Persistent storage: ${granted===true?'granted':granted===false?'not granted':'unavailable'}. ${estimate?.quota?'Estimated use '+Math.ceil(estimate.usage/1048576)+' / '+Math.floor(estimate.quota/1048576)+' MiB; allocation is not guaranteed.':''}`;
  } catch {el('storage-status').textContent='Persistent storage/estimate unavailable. Actual writes may still fail.';}
}
el('persistent').onclick=()=>storageStatus(true);
async function render() {
  const data=await store.list();el('entries').replaceChildren();
  for(const entry of data.entries) {
    const li=document.createElement('li'),text=document.createElement('span'),button=document.createElement('button');
    text.textContent=`${entry.label} · revision ${entry.revision} · ${entry.photoIds.length} photos · local draft${entry.photoIds.length?'':' (media missing)'}`;
    button.type='button';button.textContent='Review / add photos';button.onclick=()=>{
      if(busy || (dirty && !confirm('Discard these uncommitted form changes? Retained drafts will be preserved.')))return;
      current={id:entry.id,revision:entry.revision};el('label').value=entry.label;el('photos').value='';dirty=false;el('write-status').textContent='Reviewing retained draft. New changes need an explicit retain action.';
    };
    li.append(text,button);el('entries').append(li);
  }
  el('status').textContent=`Local workspace open · ${data.entries.length} retained drafts. ${data.entries.length?'':'Local data unavailable/new installation; this may also mean prior data was lost. Missing counts are unknown.'}`;
}
async function reopen() {
  if(busy)return;
  el('retain').disabled=true;store?.close();store=undefined;
  try {store=await openStore();await render();el('retain').disabled=false;navigator.serviceWorker?.controller?.postMessage({type:'ACCEPT_LOCAL_SCHEMA',version:2});}
  catch(e){el('status').textContent='Local data requires recovery. No database reset was performed. Compatible read-only salvage/export tooling is required.';error(e);}
  await storageStatus();
}
el('entry-form').onsubmit=async event=>{
  event.preventDefault();if(busy || !store)return;busy=true;el('retain').disabled=true;
  for(const control of el('entry-form').elements)control.disabled=true;
  el('write-status').textContent='Writing… not yet retained.';
  try {
    const selected=[...el('photos').files];if(selected.length>8)throw new Error('Select no more than 8 photos. Nothing was retained.');
    const photos=[];for(const file of selected)photos.push(await normalizePhoto(file,el('role').value));
    const entry=await store.commit({id:current.id,expectedRevision:current.revision,label:el('label').value,photos});
    current={id:entry.id,revision:entry.revision};dirty=false;el('photos').value='';
    await render();el('write-status').textContent='Retained on this phone. Local evidence only; no recovery copy verified.';
  } catch(e){error(e);}
  finally {busy=false;for(const control of el('entry-form').elements)control.disabled=false;el('retain').disabled=!store;await storageStatus();}
};
el('new').onclick=()=>{
  if(busy || (dirty && !confirm('Discard uncommitted form changes? Retained drafts will be preserved.')))return;
  current={id:crypto.randomUUID(),revision:0};el('entry-form').reset();dirty=false;el('write-status').textContent='New draft; nothing retained yet.';
};
function workerMessage(worker) {
  return new Promise(resolve=>{
    const channel=new MessageChannel(),timer=setTimeout(()=>resolve(false),2000);
    channel.port1.onmessage=e=>{clearTimeout(timer);channel.port1.close();resolve(e.data?.complete===true);};
    worker.postMessage({type:'CHECK_SHELL'},[channel.port2]);
  });
}
async function shellStatus() {
  if(!('serviceWorker' in navigator)){el('shell-status').textContent='Service workers unavailable. First setup requires trusted HTTPS.';return;}
  const worker=navigator.serviceWorker.controller;
  el('shell-status').textContent=worker && await workerMessage(worker)?'Complete cached shell controls this window. Device/security acceptance remains pending.':'No verified controlling shell. First setup is required; offline startup is not established.';
}
el('prepare').onclick=async()=>{
  if(dirty || busy){el('shell-status').textContent='Update deferred: retain or discard uncommitted changes first.';return;}
  el('prepare').disabled=true;el('shell-status').textContent='Preparing shell using authorized foreground requests…';
  try {
    if(!isSecureContext || !('serviceWorker' in navigator))throw new Error('Trusted secure origin required');
    let reg=await navigator.serviceWorker.getRegistration('/offline-coin-show/');
    if(reg)await reg.update();
    else reg=await navigator.serviceWorker.register('/offline-coin-show/sw.js',{scope:'/offline-coin-show/',updateViaCache:'none'});
    const candidate=reg.installing || reg.waiting || reg.active;
    if(!candidate)throw new Error('No worker');
    if(candidate.state==='installing')await new Promise((ok,no)=>{
      const timer=setTimeout(()=>no(new Error('Installation timeout')),80000);
      candidate.addEventListener('statechange',()=>{if(candidate.state==='installed' || candidate.state==='activated'){clearTimeout(timer);ok();}else if(candidate.state==='redundant'){clearTimeout(timer);no(new Error('Installation rejected'));}});
    });
    if(!await workerMessage(candidate))throw new Error('Incomplete shell');
    el('shell-status').textContent='Complete shell prepared. Close all app windows and reopen to use it. Device/security acceptance pending.';
  } catch {el('shell-status').textContent='Shell preparation/update failed. Authorization or network/integrity checks did not succeed. Previous shell and local data were preserved. Re-pair at the approved host if required.';}
  finally{el('prepare').disabled=false;}
};
addEventListener('pageshow',()=>{if(!busy)reopen();});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible' && !busy)reopen();});
await reopen();shellStatus().catch(()=>{el('shell-status').textContent='Shell status unavailable. Local data remains independent.';});
