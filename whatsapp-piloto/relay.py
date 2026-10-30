"""Fila persistente e transferência independente de mídias, por grupo autorizado."""
import os, json, sqlite3, time, threading, hashlib, hmac, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

MAX_BODY=28*1024*1024
WAKE=threading.Event()
@contextmanager
def connection():
    db=sqlite3.connect(Path(os.environ.get('STATE_DIR','/data'))/'fila.sqlite',timeout=30)
    db.execute('pragma journal_mode=WAL')
    db.execute('pragma synchronous=FULL')
    db.execute('create table if not exists fila (id text primary key, corpo text, tentativas integer default 0, proxima real default 0)')
    db.execute('create table if not exists midia_retry (id text primary key, tentativas integer default 0, proxima real default 0)')
    db.execute('create table if not exists estado (chave text primary key, valor real)')
    try:yield db
    finally:db.close()

def request(url,headers,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,headers={**headers,'Content-Type':'application/json'},data=data)
    with urllib.request.urlopen(req,timeout=40) as r:
        raw=r.read(MAX_BODY+1)
        if len(raw)>MAX_BODY:raise ValueError('limite')
        return json.loads(raw)

def gateway(route,body):
    return request(os.environ['GATEWAY_URL']+route,{'Authorization':'Bearer '+os.environ['INGEST_TOKEN']},body)

def evolution(route,body=None):
    return request(os.environ.get('EVOLUTION_URL','http://localhost:8080')+route,{'apikey':os.environ['EVOLUTION_API_KEY']},body)

def sanitize(payload,allowed):
    if payload.get('instance')!='piloto-secundario':raise ValueError('instancia')
    event=str(payload.get('event','')).lower().replace('_','.')
    if event=='send.message':event='messages.upsert'
    if event not in ['messages.upsert','messages.set','messages.delete']:return None
    data=payload.get('data',[])
    if isinstance(data,dict):data=data.get('messages',[data])
    if not isinstance(data,list) or len(data)>5000:raise ValueError('lote')
    records=[]
    for m in data:
        key=m.get('key',m)
        if key.get('remoteJid') not in allowed:continue
        # Somente os campos necessários. Tokens e chaves de download ficam na Evolution.
        def clean(value):
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ['apikey','url','directPath','mediaKey','fileEncSha256','base64']}
            if isinstance(value,list):return [clean(v) for v in value]
            return value
        records.append(clean({k:v for k,v in m.items() if k in ['key','id','remoteJid','participant','fromMe','message','messageTimestamp']}))
    return {'event':event,'instance':'piloto-secundario','data':records} if records else None

def enqueue(db,payload):
    body=json.dumps(payload,sort_keys=True,separators=(',',':'))
    with db:db.execute('insert or ignore into fila(id,corpo) values (?,?)',(hashlib.sha256(body.encode()).hexdigest(),body))
    WAKE.set()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,data):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path!='/health':return self.respond(404,{})
        with connection() as db:
            n=db.execute('select count(*) from fila').fetchone()[0]
            state=dict(db.execute('select chave,valor from estado'))
        self.respond(200,{'status':'ok','fila':n,**state})
    def do_POST(self):
        if self.path!='/webhook':return self.respond(404,{})
        expected='Bearer '+os.environ['LOCAL_WEBHOOK_TOKEN']
        if not hmac.compare_digest(self.headers.get('Authorization',''),expected):return self.respond(401,{})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=MAX_BODY:return self.respond(413,{})
            payload=json.loads(self.rfile.read(size))
            allowed=set(filter(None,os.environ.get('ALLOWED_GROUPS','').split(',')))
            payload=sanitize(payload,allowed)
            with connection() as db:
                with db:db.execute("insert into estado values('ultimo_webhook',?) on conflict(chave) do update set valor=excluded.valor",(time.time(),))
                if payload:enqueue(db,payload)
            self.respond(202,{'recebido':True})
        except (ValueError,TypeError,AttributeError):self.respond(400,{'erro':'evento_invalido'})
        except Exception:self.respond(503,{'erro':'fila_indisponivel'})

def worker_once():
    now=time.time()
    with connection() as db:
        for key,body,attempts in db.execute('select id,corpo,tentativas from fila where proxima<=? order by proxima limit 20',(now,)).fetchall():
            try:
                gateway('/webhook',json.loads(body))
                with db:
                    db.execute('delete from fila where id=?',(key,))
                    db.execute("insert into estado values('ultima_entrega_supabase',?) on conflict(chave) do update set valor=excluded.valor",(time.time(),))
            except Exception:
                with db:db.execute('update fila set tentativas=tentativas+1,proxima=? where id=?',(now+min(3600,2**min(attempts+1,12)),key))

def transfer_media(row):
    now=time.time()
    with connection() as db:
        state=db.execute('select tentativas,proxima from midia_retry where id=?',(row['id'],)).fetchone()
        if state and state[1]>now:return
        try:
            media=evolution('/chat/getBase64FromMediaMessage/piloto-secundario',{'message':{'key':{'id':row['mensagem_id'],'remoteJid':row['grupo_jid']}},'convertToMp4':False})
            if not media or not media.get('base64'):raise ValueError('midia_indisponivel')
            b64=media['base64']
            if b64.startswith('data:'):b64=b64.split(',',1)[1]
            gateway('/media',{'id':row['id'],'base64':b64})
            with db:db.execute('delete from midia_retry where id=?',(row['id'],))
        except Exception:
            try:gateway('/media',{'id':row['id'],'erro':True})
            except Exception:pass
            n=(state[0] if state else 0)+1
            with db:db.execute('insert into midia_retry values(?,?,?) on conflict(id) do update set tentativas=excluded.tentativas,proxima=excluded.proxima',(row['id'],n,now+min(86400,2**min(n+5,17))))

def media_worker_once():
    rows=gateway('/pending',{'limit':2})
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(transfer_media,rows))

def worker():
    while True:
        WAKE.clear()
        try:worker_once()
        except Exception:print(json.dumps({'evento':'retry_backend'}),flush=True)
        WAKE.wait(1)

def media_worker():
    while True:
        try:media_worker_once()
        except Exception:print(json.dumps({'evento':'retry_midia'}),flush=True)
        time.sleep(2)

if __name__=='__main__':
    os.umask(0o077)
    if not os.environ.get('LOCAL_WEBHOOK_TOKEN') or len(os.environ['LOCAL_WEBHOOK_TOKEN'])<32:raise SystemExit('Configure o token local.')
    threading.Thread(target=worker,daemon=True).start()
    threading.Thread(target=media_worker,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',8090),Handler).serve_forever()
