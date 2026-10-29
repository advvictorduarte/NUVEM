import { createHandler } from './core.mjs';
const base=Deno.env.get('SUPABASE_URL')!;
const secret=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const headers={apikey:secret,Authorization:`Bearer ${secret}`,'content-type':'application/json'};
async function api(path:string,options:RequestInit={}) {
 const r=await fetch(base+path,{...options,headers:{...headers,...options.headers}});
 if(!r.ok) throw new Error('backend');
 const text=await r.text(); return text?JSON.parse(text):null;
}
const db={
 rpc:(name:string,args:unknown)=>api('/rest/v1/rpc/'+name,{method:'POST',body:JSON.stringify(args)}),
 get:(table:string,query:string)=>api('/rest/v1/'+table+'?'+query),
 insert:(table:string,value:unknown)=>api('/rest/v1/'+table,{method:'POST',body:JSON.stringify(value)}),
 patch:(table:string,query:string,value:unknown)=>api('/rest/v1/'+table+'?'+query,{method:'PATCH',body:JSON.stringify(value)}),
};
const storage={
 async put(key:string,bytes:Uint8Array,mime:string){
  const r=await fetch(base+'/storage/v1/object/whatsapp-teste/'+key,{method:'POST',headers:{...headers,'content-type':mime,'x-upsert':'true'},body:bytes});
  if(!r.ok)throw new Error('storage');
 },
 async sign(key:string,seconds:number){
  const data=await api('/storage/v1/object/sign/whatsapp-teste/'+key,{method:'POST',body:JSON.stringify({expiresIn:seconds,download:'arquivo'})});
  return base+'/storage/v1'+data.signedURL;
 }
};
Deno.serve(createHandler({db,storage,authorize:(purpose:string,hash:string)=>db.rpc('autorizar_gateway',{finalidade_arg:purpose,hash_arg:hash})}));
