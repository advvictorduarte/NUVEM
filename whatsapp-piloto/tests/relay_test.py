import importlib.util,unittest,tempfile,os,json
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('relay',Path(__file__).resolve().parents[1]/'relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)
JID='120000000000001@g.us'
def event():
 return {'instance':'piloto-secundario','apikey':'SECRETO','event':'MESSAGES_UPSERT','data':[{'key':{'remoteJid':JID,'id':'1'},'message':{'imageMessage':{'url':'secreto','mediaKey':'secreto','caption':'ficticio'}}}]}
class RelayTest(unittest.TestCase):
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
    with self.assertRaises(RuntimeError):relay.worker_once()
   with relay.connection() as db:
    self.assertEqual(db.execute('select tentativas from fila').fetchone()[0],1)
    db.execute('update fila set proxima=0');db.commit()
   with patch.object(relay,'gateway',return_value=[]):relay.worker_once()
   with relay.connection() as db:self.assertEqual(db.execute('select count(*) from fila').fetchone()[0],0)
if __name__=='__main__':unittest.main()
