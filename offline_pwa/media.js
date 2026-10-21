import {LIMITS,LocalStoreError,sha256} from './storage.js';
const reject=message=>{throw new LocalStoreError('unsupported-photo',message);};
function dimensions(bytes) {
  const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  if(bytes.length>=24 && bytes.slice(0,8).every((b,i)=>b===[137,80,78,71,13,10,26,10][i])) {
    let at=8;
    while(at+12<=bytes.length) {
      const length=v.getUint32(at), type=String.fromCharCode(...bytes.slice(at+4,at+8));
      if(type==='acTL')reject('Animated PNG is unsupported. Retake or select a still JPEG/PNG.');
      if(at+12+length>bytes.length)reject('Truncated PNG. Retake or select another photo.');
      at+=length+12;
    }
    return [v.getUint32(16),v.getUint32(20)];
  }
  if(bytes[0]===255 && bytes[1]===216) {
    let at=2;
    while(at+4<=bytes.length) {
      if(bytes[at++]!==255)break;
      while(bytes[at]===255)at++;
      const marker=bytes[at++];
      if(marker===217 || marker===218)break;
      if(marker===1 || (marker>=208 && marker<=215))continue;
      const length=v.getUint16(at);
      if(length<2 || at+length>bytes.length)break;
      if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker) && length>=8)return [v.getUint16(at+5),v.getUint16(at+3)];
      at+=length;
    }
  }
  reject('Unsupported or damaged photo. HEIC/HEIF is unsupported; retake or select JPEG/PNG.');
}
export async function normalizePhoto(blob,role='unassigned') {
  if(!(blob instanceof Blob) || blob.size===0 || blob.size>LIMITS.photoBytes)reject('Select a JPEG/PNG photo up to 16 MiB. Nothing was retained.');
  if(!['unassigned','obverse','reverse','detail'].includes(role))reject('Select an explicit photo role.');
  const bytes=new Uint8Array(await blob.arrayBuffer()), [width,height]=dimensions(bytes);
  if(!width || !height || width>8000 || height>8000 || width*height>30000000)reject('Photo exceeds 30 MP or 8000 pixels per edge. No resizing was performed.');
  let image,objectUrl;
  try {
    const typed=new Blob([bytes],{type:bytes[0]===255?'image/jpeg':'image/png'});
    if(globalThis.createImageBitmap)image=await createImageBitmap(typed);
    else {objectUrl=URL.createObjectURL(typed);image=new Image();image.src=objectUrl;await image.decode();}
    const w=image.width || image.naturalWidth,h=image.height || image.naturalHeight;
    if(w>8000 || h>8000 || w*h>30000000)reject('Decoded photo exceeds supported dimensions.');
    const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
    canvas.getContext('2d').drawImage(image,0,0);
    const normalized=await new Promise(ok=>canvas.toBlob(ok,'image/png'));
    if(!normalized || normalized.size>LIMITS.photoBytes)reject('Normalized photo exceeds 16 MiB. No quota compression or resizing was performed.');
    return {id:crypto.randomUUID(),blob:normalized,size:normalized.size,sha256:await sha256(normalized),width:w,height:h,role};
  } catch(e) {if(e instanceof LocalStoreError)throw e;reject('Photo could not be decoded. Retake or select a still JPEG/PNG.');}
  finally {image?.close?.();if(objectUrl)URL.revokeObjectURL(objectUrl);}
}
