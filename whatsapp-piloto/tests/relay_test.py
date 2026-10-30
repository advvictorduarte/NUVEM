import importlib.util,unittest,tempfile,os,json,threading,io
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('relay',Path(__file__).resolve().parents[1]/'relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)
JID='120000000000001@g.us'
def event():
 return {'instance':'piloto-secundario','apikey':'SECRETO','event':'MESSAGES_UPSERT','data':[{'key':{'remoteJid':JID,'id':'1'},'message':{'imageMessage':{'url':'secreto','mediaKey':'secreto','caption':'ficticio'}}}]}
class RelayTest(unittest.TestCase):
 def test_envio_pela_evolution_normalizado(self):
  e=event();e['event']='SEND_MESSAGE'
  self.assertEqual(relay.sanitize(e,{JID})['event'],'messages.upsert')
 def test_lista_vazia_bloqueia_tudo(self):self.assertIsNone(relay.sanitize(event(),set()))
 def test_segredos_removidos(self):
  data=relay.sanitize(event(),{JID});self.assertNotIn('secreto',json.dumps(data));self.assertNotIn('SECRETO',json.dumps(data))
 def test_instancia_principal_bloqueada(self):
  e=event();e['instance']='principal'
  with self.assertRaises(ValueError):relay.sanitize(e,{JID})
 def test_fila_persistente_deduplicada(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'STATE_DIR':d}):
   with relay.connection() as db:relay.enqueue(db,event());relay.enqueue(db,event())
   with relay.connection() as db:self.assertEqual(db.execute('select count(*) from fila').fetchone()[0],1)
 def test_erro_preserva_fila_e_sucesso_remove(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'STATE_DIR':d}):
   with relay.connection() as db:relay.enqueue(db,event())
   with patch.object(relay,'gateway',side_effect=RuntimeError):
    relay.worker_once()
   with relay.connection() as db:
    self.assertEqual(db.execute('select tentativas from fila').fetchone()[0],1)
    db.execute('update fila set proxima=0');db.commit()
   with patch.object(relay,'gateway',return_value=[]):relay.worker_once()
   with relay.connection() as db:self.assertEqual(db.execute('select count(*) from fila').fetchone()[0],0)
 def test_download_lento_nao_bloqueia_entrega_de_nova_mensagem(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'STATE_DIR':d}):
   with relay.connection() as db:relay.enqueue(db,event())
   downloading=threading.Event();release=threading.Event();delivered=threading.Event()
   def fake_gateway(route,body):
    if route=='/pending':return [{'id':'fake','mensagem_id':'fake','grupo_jid':JID}]
    if route=='/webhook':delivered.set()
    return {}
   def fake_evolution(*args):
    downloading.set();release.wait(5);return {'base64':'eA=='}
   with patch.object(relay,'gateway',side_effect=fake_gateway),patch.object(relay,'evolution',side_effect=fake_evolution):
    media=threading.Thread(target=relay.media_worker_once);media.start()
    try:
     self.assertTrue(downloading.wait(2))
     queue=threading.Thread(target=relay.worker_once);queue.start()
     self.assertTrue(delivered.wait(1),'Mensagem nova aguardou o download antigo')
    finally:release.set();media.join(3);queue.join(3)

class WebhookTest(unittest.TestCase):
 def test_reaplica_e_confirma_sem_expor_token(self):
  spec=importlib.util.spec_from_file_location('ativar',Path(__file__).resolve().parents[1]/'scripts/ativar_tempo_real.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  saved={'enabled':True,'url':'http://relay:8090/webhook','events':module.EVENTS,'headers':{'Authorization':'Bearer segredo-ficticio'}}
  with tempfile.TemporaryDirectory() as d,patch.object(module,'ROOT',Path(d)),patch.dict(os.environ,{},clear=True),patch.object(module,'evolution',side_effect=[None,{},saved]):
   (Path(d)/'.env').write_text('LOCAL_WEBHOOK_TOKEN=segredo-ficticio\nALLOWED_GROUPS=123@g.us\n')
   out=io.StringIO()
   with redirect_stdout(out):module.configure(JID)
   self.assertIn(JID,(Path(d)/'.env').read_text())
   self.assertIn('123@g.us',(Path(d)/'.env').read_text())
   self.assertNotIn('segredo-ficticio',out.getvalue())
if __name__=='__main__':unittest.main()
