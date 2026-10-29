"""Operações manuais exclusivamente na instância piloto. Sem envio de mensagens."""
import sys,os,json,argparse
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from relay import evolution,gateway
for line in (root/'.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
os.environ['EVOLUTION_URL']='http://127.0.0.1:8080'
p=argparse.ArgumentParser();p.add_argument('acao',choices=['criar','estado','grupos','historico']);p.add_argument('--confirmo-numero-secundario',action='store_true');p.add_argument('--grupo');args=p.parse_args()
if args.acao=='criar':
 if not args.confirmo_numero_secundario:raise SystemExit('Confirme que usará um número secundário exclusivo de testes, sem dados de clientes.')
 payload={'instanceName':'piloto-secundario','integration':'WHATSAPP-BAILEYS','qrcode':False,'groupsIgnore':False,'syncFullHistory':True,'readMessages':False,'readStatus':False,'alwaysOnline':False,
  'webhook':{'enabled':True,'url':'http://relay:8090/webhook','byEvents':False,'base64':False,'headers':{'Authorization':'Bearer '+os.environ['LOCAL_WEBHOOK_TOKEN']},'events':['MESSAGES_UPSERT','MESSAGES_SET','MESSAGES_DELETE']}}
 evolution('/instance/create',payload)
 print('Instância criada. No Manager local, conecte somente o número secundário autorizado.')
elif args.acao=='estado':print(json.dumps(evolution('/instance/connectionState/piloto-secundario')))
elif args.acao=='grupos':
 for g in evolution('/group/fetchAllGroups/piloto-secundario?getParticipants=false'):
  print(json.dumps({'jid':g.get('id'),'nome':g.get('subject')},ensure_ascii=False))
elif args.acao=='historico':
 if args.grupo not in os.environ.get('ALLOWED_GROUPS','').split(','):raise SystemExit('Grupo não autorizado no relay.')
 total=0
 for page in range(1,1001):
  data=evolution('/chat/findMessages/piloto-secundario',{'where':{'key':{'remoteJid':args.grupo}},'page':page,'offset':100})
  rows=data.get('messages',{}).get('records',[])
  if not rows:break
  gateway('/webhook',{'instance':'piloto-secundario','event':'messages.set','data':rows});total+=len(rows)
  pages=data.get('messages',{}).get('pages')
  if pages and page>=pages:break
 else:raise SystemExit('Limite de paginação atingido; histórico incompleto.')
 print(json.dumps({'recebidas':total,'aviso':'Apenas histórico disponível na Evolution; não garante todo o histórico do celular.'},ensure_ascii=False))
