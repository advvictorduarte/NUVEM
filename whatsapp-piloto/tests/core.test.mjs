import test from 'node:test';
import assert from 'node:assert/strict';
import {normalize,createHandler,sha256} from '../supabase/functions/whatsapp-gateway/core.mjs';
const jid='120000000000001@g.us';
const raw={key:{id:'FICTICIO1',remoteJid:jid,participant:'participante-ficticio'},messageTimestamp:1793268000,message:{conversation:'Contrato fictício'}};
test('normaliza texto e proveniência sem guardar apikey',()=>{
 const n=normalize({event:'MESSAGES_UPSERT',data:raw,apikey:'segredo'});
 assert.equal(n.records[0].texto,'Contrato fictício');assert.equal(n.records[0].mensagem_id,'FICTICIO1');
 assert.equal(JSON.stringify(n).includes('segredo'),false);
});
test('histórico aceita lista; conversas pessoais são descartadas',()=>{
 const n=normalize({event:'messages.set',data:[raw,{...raw,key:{...raw.key,remoteJid:'pessoal@s.whatsapp.net'}}]});
 assert.equal(n.received,2);assert.equal(n.records.length,1);
});
test('áudio, imagem, PDF e documento são pendências, sem guardar URL de download',()=>{
 for(const t of ['audioMessage','imageMessage','documentMessage','videoMessage']){
  const n=normalize({event:'messages.upsert',data:{...raw,message:{[t]:{mimetype:'application/pdf',fileName:'ficticio.pdf',url:'https://segredo',caption:'Legenda'}}}});
  assert.equal(n.records[0].midia_status,'pendente');assert.equal(JSON.stringify(n).includes('https://'),false);
 }
});
test('não arquiva visualização única',()=>{
 assert.equal(normalize({event:'messages.upsert',data:{...raw,message:{viewOnceMessage:{message:{imageMessage:{}}}}}}).records.length,0);
});
test('marcação de exclusão e evento desconhecido',()=>{
 assert.equal(normalize({event:'messages.delete',data:raw.key}).records[0].excluida,true);
 assert.equal(normalize({event:'qrcode.updated',data:{}}).records.length,0);
});
test('hash determinístico',async()=>assert.equal((await sha256('abc')).length,64));
test('nega requisição sem token',async()=>{
 const h=createHandler({authorize:async()=>false});
 assert.equal((await h(new Request('https://teste/whatsapp-gateway/search',{method:'POST',body:'{}'}))).status,401);
});
test('token de consulta não permite ingestão e instância principal é bloqueada',async()=>{
 const h=createHandler({authorize:async purpose=>purpose==='consulta'});
 assert.equal((await h(new Request('https://teste/whatsapp-gateway/webhook',{method:'POST',headers:{authorization:'Bearer '+'x'.repeat(64)},body:'{}'}))).status,401);
 const h2=createHandler({authorize:async()=>true});
 assert.equal((await h2(new Request('https://teste/whatsapp-gateway/webhook',{method:'POST',headers:{authorization:'Bearer '+'x'.repeat(64)},body:'{"instance":"principal"}'}))).status,403);
});
test('JSON inválido não expõe conteúdo; erro de backend gera 503 para retry',async()=>{
 const h=createHandler({authorize:async()=>true,db:{rpc:async()=>{throw Error('segredo')}}});
 const req=body=>new Request('https://teste/whatsapp-gateway/webhook',{method:'POST',headers:{authorization:'Bearer '+'x'.repeat(64)},body});
 assert.equal((await h(req('invalido'))).status,400);
 const r=await h(req('{"instance":"piloto-secundario","data":[]}'));assert.equal(r.status,503);assert.equal((await r.text()).includes('segredo'),false);
});
