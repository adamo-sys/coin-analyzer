// One transactional authority for local drafts and normalized photo bytes only.
export const LIMITS = Object.freeze({entries:200,photos:8,photoBytes:16*1024*1024,totalBytes:128*1024*1024,reserve:32*1024*1024});
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH=/^[0-9a-f]{64}$/;
const roles=new Set(['unassigned','obverse','reverse','detail']);
export class LocalStoreError extends Error {
  constructor(code,message) { super(message);this.name='LocalStoreError';this.code=code; }
}
const fail=(code,message)=>{throw new LocalStoreError(code,message);};
function localError(error) {
  if(error instanceof LocalStoreError)return error;
  if(error?.name==='QuotaExceededError')return new LocalStoreError('quota','Not retained: storage quota exhausted. Keep existing evidence; free unrelated space and retry after reopening.');
  if(error?.name==='VersionError')return new LocalStoreError('newer-schema','A newer database is present. Open compatible application code; no data was reset.');
  return new LocalStoreError('recovery-required','Local operation failed. Preserve this origin and reopen compatible code for recovery; no automatic reset or retry.');
}
const request=r=>new Promise((ok,no)=>{r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
async function transaction(db,names,mode,action) {
  let tx;
  try { tx=db.transaction(names,mode,{durability:mode==='readwrite'?'strict':'default'}); }
  catch(e) { if(e.name!=='TypeError')throw localError(e);tx=db.transaction(names,mode); }
  const done=new Promise((ok,no)=>{tx.oncomplete=ok;tx.onabort=()=>no(tx.error || new DOMException('Aborted','AbortError'));});
  done.catch(()=>{});
  try {const result=await action(tx);await done;return result;}
  catch(e) {try{tx.abort();}catch{}await done.catch(()=>{});throw localError(e);}
}
export const sha256=async blob=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');

function photoShape(photo) {
  return UUID.test(photo.id) && UUID.test(photo.entryId) && photo.blob instanceof Blob &&
    photo.blob.type==='image/png' && photo.blob.size>0 && photo.blob.size<=LIMITS.photoBytes &&
    photo.size===photo.blob.size && HASH.test(photo.sha256) && roles.has(photo.role) &&
    Number.isInteger(photo.width) && Number.isInteger(photo.height) && photo.width>0 && photo.height>0 &&
    photo.width<=8000 && photo.height<=8000 && photo.width*photo.height<=30000000;
}
function entryShape(entry) {
  return UUID.test(entry.id) && Number.isSafeInteger(entry.revision) && entry.revision>0 &&
    typeof entry.label==='string' && entry.label.length>0 && entry.label.length<=160 && entry.state==='draft' &&
    Array.isArray(entry.photoIds) && entry.photoIds.length<=LIMITS.photos &&
    new Set(entry.photoIds).size===entry.photoIds.length && entry.photoIds.every(id=>UUID.test(id));
}
async function validate(data) {
  if(data.entries.length>LIMITS.entries || data.schema?.value!==2)fail('recovery-required','Local schema or limits are invalid. Preserve data for compatible recovery.');
  const map=new Map(data.photos.map(p=>[p.id,p])), references=new Set();
  let total=0;
  for(const entry of data.entries) {
    if(!entryShape(entry))fail('recovery-required','Local entry is incompatible. Preserve data for recovery.');
    for(const id of entry.photoIds) {
      const photo=map.get(id);
      if(!photo || photo.entryId!==entry.id || references.has(id))fail('recovery-required','A local photo reference is invalid. Preserve data; no reset was performed.');
      references.add(id);
    }
  }
  for(const photo of data.photos) {
    if(!references.has(photo.id) || !photoShape(photo) || await sha256(photo.blob)!==photo.sha256)fail('recovery-required','Local photo integrity failed. Preserve this origin for read-only recovery with compatible code.');
    total+=photo.size;
  }
  if(total>LIMITS.totalBytes)fail('recovery-required','Local storage exceeds this version’s supported limit. Use compatible recovery code.');
  return data;
}

export async function openStore(name='coin-show-local') {
  if(!globalThis.indexedDB)fail('unavailable','IndexedDB unavailable; nothing can be retained.');
  let db;
  try {
    db=await new Promise((ok,no)=>{
      let settled=false,upgrade;
      const r=indexedDB.open(name,2);
      const reject=e=>{if(!settled){settled=true;clearTimeout(timer);no(e);}};
      const timer=setTimeout(()=>{
        if(settled)return;
        // Reject only when cancellation can still prevent the schema commit.
        // A native commit can precede delivery of the open-success event.
        if(upgrade){try{upgrade.abort();}catch{return;}}
        reject(new LocalStoreError('blocked','Local database open timed out. Close other windows, preserve data and reopen.'));
      },5000);
      r.onblocked=()=>reject(new LocalStoreError('blocked','Database upgrade blocked. Close other app windows and reopen; no reset.'));
      r.onerror=()=>reject(r.error);
      r.onupgradeneeded=event=>{
        if(settled){r.transaction.abort();return;}
        const d=r.result,t=r.transaction;
        upgrade=t;
        t.oncomplete=()=>clearTimeout(timer);
        if(event.oldVersion===0) {
          d.createObjectStore('entries',{keyPath:'id'});d.createObjectStore('photos',{keyPath:'id'});
        }
        if(event.oldVersion===1) {
          // Validate a snapshot inside the exclusive upgrade before publishing
          // state/meta. Hashing awaits non-IDB work: retain a pending request
          // until it finishes, then write only from an active request callback.
          if(!d.objectStoreNames.contains('entries') || !d.objectStoreNames.contains('photos')) {t.abort();return;}
          const entries=t.objectStore('entries'),photos=t.objectStore('photos');
          let active=true,validated;
          t.addEventListener('abort',()=>{active=false;});
          const abort=e=>{if(!active)return;active=false;try{t.abort();}catch{}reject(e);};
          Promise.all([request(entries.getAll()),request(photos.getAll())]).then(async ([old,media])=>{
            if(old.some(e=>Object.hasOwn(e,'state')))fail('recovery-required','Legacy entry state is incompatible. Preserve data for recovery.');
            const data={entries:old.map(e=>({...e,state:'draft'})),photos:media,schema:{key:'schema',value:2}};
            await validate(data);
            if(active && !settled)validated=data;
          }).catch(abort);
          const pump=()=>{
            if(!active || settled)return;
            const pending=entries.get(0);
            pending.onsuccess=()=>{
              if(!active || settled)return;
              if(!validated){pump();return;}
              try {
                for(const e of validated.entries)entries.put(e);
                d.createObjectStore('meta',{keyPath:'key'}).put(validated.schema);
              }catch(e){abort(e);}
            };
          };
          pump();
        }
        if(event.oldVersion===0) d.createObjectStore('meta',{keyPath:'key'}).put({key:'schema',value:2});
      };
      r.onsuccess=()=>{if(settled){r.result.close();return;}settled=true;clearTimeout(timer);ok(r.result);};
    });
    let closed=false, healthy=true;
    db.onversionchange=()=>{closed=true;db.close();};
    db.onclose=()=>{closed=true;};
    const ensure=()=>{if(closed || !healthy)fail('recovery-required','Connection closed or recovery required. Reopen before further changes.');};
    async function list() {
      ensure();
      try {
        const data=await transaction(db,['entries','photos','meta'],'readonly',async t=>{
          const [entries,photos,schema]=await Promise.all([request(t.objectStore('entries').getAll()),request(t.objectStore('photos').getAll()),request(t.objectStore('meta').get('schema'))]);
          return {entries,photos,schema};
        });
        return await validate(data);
      } catch(e) {healthy=false;throw localError(e);}
    }
    await list();
    return {
      list,
      close(){closed=true;db.close();},
      async commit({id,expectedRevision,label,photos=[]}) {
        ensure();
        if(!UUID.test(id) || !Number.isSafeInteger(expectedRevision) || expectedRevision<0 || typeof label!=='string' || !label.trim() || label.trim().length>160 || !Array.isArray(photos) || photos.length>LIMITS.photos)fail('invalid-input','Draft fields exceed supported limits. Nothing was retained.');
        const prepared=[];
        for(const photo of photos) {
          const record={id:photo.id,entryId:id,blob:photo.blob,size:photo.blob?.size,sha256:photo.sha256,role:photo.role,width:photo.width,height:photo.height};
          if(!photoShape(record) || await sha256(record.blob)!==record.sha256)fail('invalid-input','Photo is invalid; select a supported normalized photo again.');
          prepared.push(record);
        }
        const estimate=await navigator.storage?.estimate?.().catch(()=>null);
        const added=prepared.reduce((n,p)=>n+p.size,0);
        if(estimate && Number.isFinite(estimate.quota) && Number.isFinite(estimate.usage) && estimate.quota-estimate.usage<added+LIMITS.reserve)fail('quota','Not retained: insufficient estimated headroom including temporary recovery/update reserve. No existing photos were removed.');
        await list(); // Validate current committed evidence before a mutation.
        const committed=await transaction(db,['entries','photos'],'readwrite',async t=>{
          const entries=t.objectStore('entries'),media=t.objectStore('photos');
          const [old,count,inventory]=await Promise.all([request(entries.get(id)),request(entries.count()),request(media.getAll())]);
          if((old?.revision || 0)!==expectedRevision)fail('revision-conflict','Another window changed this draft. Reopen and review before editing.');
          if(!old && count>=LIMITS.entries)fail('quota','Local entry limit reached. No entries were evicted.');
          const photoIds=[...(old?.photoIds || []),...prepared.map(p=>p.id)];
          if(photoIds.length>LIMITS.photos || new Set(photoIds).size!==photoIds.length || prepared.some(p=>inventory.some(f=>f.id===p.id)))fail('invalid-input','Too many or duplicate photo references. Nothing was retained.');
          if(inventory.reduce((n,p)=>n+p.size,0)+added>LIMITS.totalBytes)fail('quota','Local photo cap reached. Existing photos were preserved.');
          const value={id,revision:expectedRevision+1,label:label.trim(),state:'draft',photoIds};
          for(const p of prepared)media.put(p);
          entries.put(value);return value;
        });
        // Commit acknowledgment requires a new validated read transaction.
        try {
          const check=await list();
          const actual=check.entries.find(e=>e.id===id);
          if(!actual || actual.revision<committed.revision)throw new Error('Readback missing');
        } catch {healthy=false;fail('outcome-uncertain','Write may have committed but readback failed. Reopen and inspect the same draft before retrying; no duplicate was created automatically.');}
        return committed;
      }
    };
  } catch(e) {db?.close();throw localError(e);}
}
