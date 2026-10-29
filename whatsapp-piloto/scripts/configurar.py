"""Gera .env privado. Não cria instância, não contrata VPS e não mostra QR Code."""
import secrets,os,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
p=root/'.env'
if p.exists():raise SystemExit('.env existente preservado.')
os.umask(0o077)
cfg=json.load(open(sys.argv[1])) if len(sys.argv)>1 else None
url=cfg['url'] if cfg else input('URL do gateway: ').strip()
from getpass import getpass
token=cfg['ingestao'] if cfg else getpass('Token de ingestao: ').strip()
if not url.startswith('https://') or len(token)<32:raise SystemExit('Configuracao invalida.')
values={'GATEWAY_URL':url,'INGEST_TOKEN':token,'LOCAL_WEBHOOK_TOKEN':secrets.token_hex(32),'EVOLUTION_API_KEY':secrets.token_hex(32),'POSTGRES_PASSWORD':secrets.token_hex(24),'ALLOWED_GROUPS':''}
p.write_text(''.join(k+'='+v+'\n' for k,v in values.items()));p.chmod(0o600)
print('.env criado. Nenhum grupo autorizado no relay; a lista vazia bloqueia toda captura.')
