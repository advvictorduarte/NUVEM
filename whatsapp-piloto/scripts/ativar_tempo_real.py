"""Autoriza grupo local e reaplica/verifica webhook sem exibir chaves ou mensagens."""
import argparse,json,os,re,sys,hmac
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from relay import evolution

EVENTS=['MESSAGES_UPSERT','MESSAGES_SET','MESSAGES_DELETE','SEND_MESSAGE']
def configure(group):
    if not re.fullmatch(r'[0-9]+(?:-[0-9]+)?@g\.us',group):raise ValueError('JID inválido')
    path=ROOT/'.env'
    lines=path.read_text().splitlines()
    for line in lines:
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ[key]=value
    os.environ['EVOLUTION_URL']='http://127.0.0.1:8080'
    old=evolution('/webhook/find/piloto-secundario') or {}
    if 'webhook' in old:old=old['webhook'] or {}
    print(json.dumps({'etapa':'webhook_anterior','ativo':old.get('enabled',False),'destino_correto':old.get('url')=='http://relay:8090/webhook','eventos':old.get('events',[])},ensure_ascii=False))
    expected='Bearer '+os.environ['LOCAL_WEBHOOK_TOKEN']
    payload={'webhook':{'enabled':True,'url':'http://relay:8090/webhook','byEvents':False,'base64':False,'headers':{'Authorization':expected},'events':EVENTS}}
    evolution('/webhook/set/piloto-secundario',payload)
    saved=evolution('/webhook/find/piloto-secundario') or {}
    if 'webhook' in saved:saved=saved['webhook'] or {}
    actual_headers=saved.get('headers') or {}
    if isinstance(actual_headers,str):actual_headers=json.loads(actual_headers)
    auth=next((v for k,v in actual_headers.items() if k.lower()=='authorization'),'')
    valid=(saved.get('enabled') is True and saved.get('url')==payload['webhook']['url']
           and not saved.get('webhookByEvents',saved.get('byEvents',False))
           and set(EVENTS).issubset(saved.get('events',[])) and hmac.compare_digest(auth,expected))
    if not valid:raise RuntimeError('A Evolution não confirmou a configuração; não prossiga.')
    groups=set(filter(None,os.environ.get('ALLOWED_GROUPS','').split(',')));groups.add(group)
    updated='ALLOWED_GROUPS='+','.join(sorted(groups))
    lines=[updated if line.startswith('ALLOWED_GROUPS=') else line for line in lines]
    if not any(line.startswith('ALLOWED_GROUPS=') for line in lines):lines.append(updated)
    path.write_text('\n'.join(lines)+'\n');path.chmod(0o600)
    print(json.dumps({'webhook_confirmado':True,'grupo_configurado':group,'grupos_autorizados_localmente':len(groups)},ensure_ascii=False))
    print('Agora recrie somente o relay: sudo docker compose up -d --no-deps --build relay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--grupo',required=True);args=p.parse_args()
    try:configure(args.grupo)
    except Exception as e:
        print(json.dumps({'erro':type(e).__name__,'aviso':'Configuração não concluída. Não contém chaves ou mensagens.'},ensure_ascii=False));sys.exit(1)
