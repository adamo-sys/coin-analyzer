import {openStore} from './storage.js';
import {normalizePhoto} from './media.js';
const el=id=>document.getElementById(id);
let store,current={id:crypto.randomUUID(),revision:0},dirty=false,busy=false;
let baselineLabel='',unacknowledged=false;
let photoUrl,viewVersion=0,openVersion=0,renderVersion=0,retainedPhotos=[],photoIndex=0;
function clearPhoto(message='Select a retained draft to review its photos.') {
  ++viewVersion;retainedPhotos=[];photoIndex=0;
  el('retained-photo').hidden=true;el('retained-photo').removeAttribute('src');
  if(photoUrl){URL.revokeObjectURL(photoUrl);photoUrl=undefined;}
  el('photo-status').textContent=message;
  el('photo-previous').disabled=true;el('photo-next').disabled=true;
}
function showPhoto(index) {
  const photos=retainedPhotos;
  clearPhoto();retainedPhotos=photos;photoIndex=index;
  const photo=photos[index];
  if(!photo){el('photo-status').textContent='This draft has no retained photos.';return;}
  photoUrl=URL.createObjectURL(photo.blob);
  el('retained-photo').alt=`Retained photo ${index+1} of ${photos.length}: ${photo.role}`;
  el('retained-photo').src=photoUrl;el('retained-photo').hidden=false;
  el('photo-status').textContent=`Photo ${index+1} of ${photos.length} · ${photo.role}`;
  el('photo-previous').disabled=index===0;el('photo-next').disabled=index===photos.length-1;
}
async function loadPhotos() {
  clearPhoto('Loading retained photos…');
  const version=viewVersion,id=current.id,source=store;
  try {
    const data=await source.list();
    if(version!==viewVersion || source!==store || id!==current.id)return;
    const entry=data.entries.find(entry=>entry.id===id);
    if(!entry){clearPhoto('Selected draft is unavailable. Reopen and review local storage.');return;}
    const photos=new Map(data.photos.map(photo=>[photo.id,photo]));
    retainedPhotos=entry.photoIds.map(id=>photos.get(id));showPhoto(0);
  } catch {
    if(version===viewVersion)clearPhoto('Retained photos unavailable. Preserve local data and reopen for recovery.');
  }
}
el('photo-previous').onclick=()=>showPhoto(Math.max(0,photoIndex-1));
el('photo-next').onclick=()=>showPhoto(Math.min(retainedPhotos.length-1,photoIndex+1));
addEventListener('pagehide',()=>clearPhoto());
const connection=()=>{el('connection').textContent=navigator.onLine?'Network available; drafts remain local.':'Offline · drafts use local storage.';};
connection();addEventListener('online',connection);addEventListener('offline',connection);
function error(e) {el('write-status').textContent=e.message || 'Local data unavailable. Preserve this origin and reopen for recovery.';}
function beforeDeparture(event) {event.preventDefault();event.returnValue=true;}
function refreshProtection() {
  dirty=el('label').value.trim()!==baselineLabel || el('photos').files.length>0;
  if(dirty || unacknowledged)addEventListener('beforeunload',beforeDeparture);
  else removeEventListener('beforeunload',beforeDeparture);
}
function resetBaseline(label='') {
  baselineLabel=label.trim();unacknowledged=false;refreshProtection();
}
function changed(){
  refreshProtection();
  if(!unacknowledged)el('write-status').textContent=dirty?'Not retained: uncommitted changes.':'No uncommitted changes.';
}
function mayDiscard() {
  if(busy)return false;
  return !(dirty || unacknowledged) || confirm('Discard uncommitted form changes? Retained drafts will be preserved.');
}
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
  const version=++renderVersion,source=store,data=await source.list();
  if(version!==renderVersion || source!==store)return;
  el('entries').replaceChildren();
  for(const entry of data.entries) {
    const li=document.createElement('li'),text=document.createElement('span'),button=document.createElement('button');
    text.textContent=`${entry.label} · revision ${entry.revision} · ${entry.photoIds.length} photos · local draft${entry.photoIds.length?'':' (media missing)'}`;
    button.type='button';button.textContent='Review / add photos';button.onclick=()=>{
      if(!mayDiscard())return;
      current={id:entry.id,revision:entry.revision};el('label').value=entry.label;el('photos').value='';resetBaseline(entry.label);el('write-status').textContent='Reviewing retained draft. New changes need an explicit retain action.';
      loadPhotos();
    };
    li.append(text,button);el('entries').append(li);
  }
  el('status').textContent=`Local workspace open · ${data.entries.length} retained drafts. ${data.entries.length?'':'Local data unavailable/new installation; this may also mean prior data was lost. Missing counts are unknown.'}`;
  if(current.revision>0)await loadPhotos();
}
async function reopen() {
  if(busy)return;
  const version=++openVersion;clearPhoto();
  el('retain').disabled=true;store?.close();store=undefined;
  try {
    const opened=await openStore();
    if(version!==openVersion){opened.close();return;}
    store=opened;await render();
    if(version!==openVersion)return;
    el('retain').disabled=false;navigator.serviceWorker?.controller?.postMessage({type:'ACCEPT_LOCAL_SCHEMA',version:2});
  }
  catch(e){if(version!==openVersion)return;clearPhoto('Retained photos unavailable. Preserve local data and reopen for recovery.');el('status').textContent='Local data requires recovery. No database reset was performed. Compatible read-only salvage/export tooling is required.';error(e);}
  await storageStatus();
}
el('entry-form').onsubmit=async event=>{
  event.preventDefault();if(busy || !store)return;busy=true;el('retain').disabled=true;
  const previouslyUnacknowledged=unacknowledged;
  unacknowledged=true;refreshProtection();
  for(const control of el('entry-form').elements)control.disabled=true;
  el('write-status').textContent='Writing… not yet retained.';
  try {
    const selected=[...el('photos').files];if(selected.length>8)throw new Error('Select no more than 8 photos. Nothing was retained.');
    const photos=[];for(const file of selected)photos.push(await normalizePhoto(file,el('role').value));
    const entry=await store.commit({id:current.id,expectedRevision:current.revision,label:el('label').value,photos});
    current={id:entry.id,revision:entry.revision};el('photos').value='';resetBaseline(entry.label);
    await render();el('write-status').textContent='Retained on this phone. Local evidence only; no recovery copy verified.';
  } catch(e){unacknowledged=previouslyUnacknowledged || e.code==='outcome-uncertain';refreshProtection();error(e);}
  finally {busy=false;for(const control of el('entry-form').elements)control.disabled=false;el('retain').disabled=!store;await storageStatus();}
};
el('new').onclick=()=>{
  if(!mayDiscard())return;
  current={id:crypto.randomUUID(),revision:0};el('entry-form').reset();resetBaseline();el('write-status').textContent='New draft; nothing retained yet.';
  clearPhoto();
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
  if(dirty || busy || unacknowledged){el('shell-status').textContent='Update deferred: retain or discard uncommitted changes first.';return;}
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
