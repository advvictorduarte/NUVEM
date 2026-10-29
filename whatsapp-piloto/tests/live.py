"""Teste remoto com dados inventados. Requer arquivo privado com tokens; nunca imprime tokens."""
import json, sys, base64, hashlib, subprocess, uuid
cfg=json.load(open(sys.argv[1]))
def download(url,headers=None,body=None):
 config='url = '+json.dumps(url)+'\n'
 for k,v in (headers or {}).items():config+='header = '+json.dumps(k+': '+v)+'\n'
 if body is not None:config+='data = '+json.dumps(json.dumps(body))+'\n'
 r=subprocess.run(['curl','--silent','--show-error','--max-time','40','--config','-','--write-out','\n%{http_code}'],input=config.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 content,code=r.stdout.rsplit(b'\n',1)
 return int(code),content

def call(route,body=None,role='ingestao',token=None):
 headers={'Content-Type':'application/json'}
 if role:headers['Authorization']='Bearer '+(token or cfg[role])
 code,data=download(cfg['url']+route,headers,body)
 return code,json.loads(data)
def check(label,ok):
 if not ok: raise AssertionError(label)
 print('PASS',label)
jid='120000000000001@g.us'
run=uuid.uuid4().hex[:10]
ids={k:k+'-'+run for k in ['TEXTO1','HISTORICO1','PDF1','FOTO1','AUDIO1']}
def message(i,text,group=jid):
 return {'key':{'id':ids.get(i,i),'remoteJid':group,'participant':'participante-ficticio'},'messageTimestamp':1793268000,'message':{'conversation':text}}
def event(data,instance='piloto-secundario',kind='messages.upsert'):
 return {'instance':instance,'event':kind,'data':data,'apikey':'NAO_PERSISTIR_ESSE_SEGREDO'}
check('saude',call('/health')[0]==200)
check('sem token bloqueado',call('/search',{'query':'ficticio'},role=None)[0]==401)
check('token incorreto bloqueado',call('/search',{'query':'ficticio'},role='consulta',token='x'*64)[0]==401)
check('escopos separados',call('/webhook',event([]),role='consulta')[0]==401)
check('instancia principal bloqueada',call('/webhook',event([],instance='principal'))[0]==403)
data=event([message('TEXTO1','Contrato fictício de integração sem dados reais '+run),message('BLOQUEADO','INFORMACAO BLOQUEADA','120000000000002@g.us')])
status,result=call('/webhook',data);check('grava somente grupo autorizado',status==200 and result['aceitas']==1)
check('reenvio idempotente',call('/webhook',data)[1]['duplicado'] is True)
status,result=call('/search',{'query':'contrato '+run},role='consulta');check('busca com origem',status==200 and len(result['resultados'])==1 and result['resultados'][0]['mensagem_id']==ids['TEXTO1'])
status,result=call('/search',{'query':'BLOQUEADA'},role='consulta');check('grupo bloqueado nao consultavel',status==200 and not result['resultados'])
history=event([message('HISTORICO1','Histórico fictício recebido parcialmente')],kind='messages.set')
check('evento de historico',call('/webhook',history)[1]['aceitas']==1)
# Arquivos mínimos de teste. Não são arquivos de clientes.
def make_pdf():
 objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
 stream=b'BT /F1 12 Tf 20 50 Td (DOCUMENTO FICTICIO SEM CLIENTES) Tj ET'
 objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
 output=b'%PDF-1.4\n';offsets=[0]
 for i,obj in enumerate(objects,1):offsets.append(len(output));output+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
 start=len(output);output+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(('%010d 00000 n \n'%i).encode() for i in offsets[1:])
 return output+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'
pdf=make_pdf()
png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')
audio=b'RIFF'+(36+160).to_bytes(4,'little')+b'WAVEfmt '+(16).to_bytes(4,'little')+b'\x01\x00\x01\x00'+(8000).to_bytes(4,'little')+(16000).to_bytes(4,'little')+b'\x02\x00\x10\x00data'+(160).to_bytes(4,'little')+b'\0'*160
for mid,kind,mime,content in [('PDF1','documentMessage','application/pdf',pdf),('FOTO1','imageMessage','image/png',png),('AUDIO1','audioMessage','audio/wav',audio)]:
 m=message(mid,'');m['message']={kind:{'mimetype':mime,'fileName':mid,'caption':'Anexo fictício'}}
 check('metadados '+mid,call('/webhook',event(m))[0]==200)
 pending=call('/pending',{})[1]; row=next(x for x in pending if x['mensagem_id']==ids[mid])
 check('upload privado '+mid,call('/media',{'id':row['id'],'base64':base64.b64encode(content).decode()})[1]['sha256']==hashlib.sha256(content).hexdigest())
 signed=call('/file',{'id':row['id']},role='consulta')[1]
 status,downloaded=download(signed['url'])
 check('download integro '+mid,downloaded==content)
 # Mesmo caminho sem assinatura não deve permitir leitura pública.
 details=call('/message',{'id':row['id']},role='consulta')[1]
 public=cfg['url'].split('/functions/')[0]+'/storage/v1/object/public/whatsapp-teste/'+details['caminho_arquivo']
 denied=download(public)[0]!=200
 check('acesso publico negado '+mid,denied)
check('nenhuma midia deste teste pendente',not [x for x in call('/pending',{})[1] if x['mensagem_id'].endswith(run)])
print('VALIDACAO REMOTA CONCLUIDA - SOMENTE DADOS FICTICIOS')
