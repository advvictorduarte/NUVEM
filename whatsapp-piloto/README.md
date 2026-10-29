# WhatsApp Business + GPT — piloto isolado

Estado em 29/10/2026. Somente número secundário exclusivo de testes, sem conversas ou arquivos reais de clientes.

## Implantado e validado

- Projeto Supabase **whatsapp-gpt-piloto**, ref `lynpyfheouailjwqsvxl`, plano Free, banco em São Paulo. Cotação de criação: US$ 0/mês. Nenhuma contratação paga realizada; não habilitar upgrade ou serviços pagos sem autorização.
- Banco com grupos autorizados, mensagens, arquivos, eventos deduplicados, auditoria, clientes/processos ainda vazios e estrutura de fragmentos com vetor de 1536 dimensões.
- API `whatsapp-gateway` implantada, autenticada por tokens distintos de ingestão e consulta. Só hashes são guardados no banco. Chave privilegiada automática do Supabase permanece dentro da Edge Function.
- Armazenamento privado `whatsapp-teste`, limite de 20 MiB por arquivo, downloads assinados por 60 segundos.
- Busca textual em português com grupo, ID da mensagem, participante, data e evento de origem. Grupos desautorizados e mensagens excluídas ficam fora das consultas.
- Validação remota com dados inventados: autenticação, restrição de instância e grupo, deduplicação, histórico simulado, uploads/downloads íntegros de anexos e negação de acesso público.

**Não implantado/validado ainda:** VPS, Docker em execução, pareamento, captura real da Evolution/Baileys, recuperação real de histórico anterior, transcrição, OCR, extração de texto de PDF, geração de embeddings, busca semântica e conexão remota do ChatGPT. O MCP stdio e o OpenAPI são preparação; não significam que esta conversa já está conectada ao WhatsApp.

## Componentes

`WhatsApp secundário → Evolution/Baileys → relay com fila SQLite → API autenticada → Supabase`

O PostgreSQL local atende à Evolution; o banco Supabase é outro banco. Redis, banco local e relay não publicam portas. A Evolution publica só `127.0.0.1:8080`. O relay valida a instância, filtra grupos antes de gravar a fila e remove tokens/chaves de mídia do envelope. A API aplica novamente a autorização de grupo. Mídias são recuperadas localmente pela Evolution e enviadas ao bucket privado; falhas permanecem visíveis como pendências com retry. Conteúdos de visualização única não são arquivados pelo piloto.

Nenhum arquivo ou configuração do projeto de prazos foi modificado. Código novo apenas nesta pasta e na branch `whatsapp-piloto`; `main` preservada.

## Dependência imediata: VPS

É necessário disponibilizar uma VPS Ubuntu 24.04 com acesso SSH por chave. Referência técnica inicial: 2 vCPU, 4 GB RAM, 40 GB de disco. Não foi contratada VPS, nem existe acesso SSH configurado nesta execução. Não enviar senha ou chave privada pelo chat. Antes de qualquer contratação, confirmar provedor, preço total e autorização.

Na VPS exclusiva de testes, após disponibilizar acesso:

```bash
git clone --branch whatsapp-piloto --single-branch https://github.com/advvictorduarte/NUVEM.git
cd NUVEM/whatsapp-piloto
sudo bash scripts/instalar-docker-ubuntu.sh
python3 scripts/configurar.py
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
```

O configurador pede URL e token de ingestão, e cria senhas locais aleatórias em `.env` com permissão 600. O token de consulta não vai para a Evolution nem para o relay. O arquivo privado de credenciais de teste é entregue separadamente; não publique nem acrescente ao GitHub. A lista `ALLOWED_GROUPS` nasce vazia e bloqueia toda captura no relay.

Firewall: liberar SSH apenas ao IP administrativo. Não liberar 8080, 8090, 5432 ou 6379. Acesso ao Manager pelo computador administrativo:

```bash
ssh -N -L 8080:127.0.0.1:8080 USUARIO@IP_DA_VPS
```

Abrir `http://localhost:8080/manager` pelo túnel. A chave local está em `.env`; não colar no chat ou em prints. As imagens têm tags fixas; pull, compatibilidade e execução das imagens ainda precisam ser verificados na VPS. Não foi executado `docker compose up` neste ambiente, que não dispõe de Docker.

## Pareamento e autorização do grupo fictício

1. Garantir que a conta secundária esteja vazia de dados reais. Criar um grupo com participantes que concordaram em testar, texto, foto, PDF e áudio fictícios, inclusive alguns anteriores ao pareamento.
2. Executar `python3 scripts/instancia.py criar --confirmo-numero-secundario`. O script cria exclusivamente `piloto-secundario`, com webhook interno e `syncFullHistory=true`, sem leitura automática de mensagens/status e sem envio de mensagens.
3. Conectar pelo Manager somente após autorização do titular. O QR Code será lido pelo usuário em Aparelhos conectados do número secundário.
4. Listar grupos com `python3 scripts/instancia.py grupos`. A API de listagem e o formato de paginação foram conferidos no código-fonte; respostas da versão Docker ainda **não validadas**.
5. Autorizar apenas o JID do grupo fictício nos dois pontos: `ALLOWED_GROUPS` do `.env` e tabela `public.grupos` do **novo** projeto. A entrada inicial `120000000000001@g.us` é inventada; não representa um grupo real. Uma lista vazia bloqueia captura.
6. Reiniciar relay com `sudo docker compose up -d relay`. Para recuperar o que chegou à Evolution antes de autorizar o grupo, executar `python3 scripts/instancia.py historico --grupo JID_DO_GRUPO`.
7. Conferir contagens, IDs, textos e hashes dos anexos, mensagens novas, reinício de contêiner e interrupção/reconexão do backend. Verificar novamente a configuração de webhook após reinício. Só depois considerar outra etapa.

Autorização no SQL Editor exclusivamente do novo projeto:

```sql
insert into public.grupos(instancia,jid,nome,autorizado)
values ('piloto-secundario','JID_REAL_DO_GRUPO_FICTICIO','TESTE SEM CLIENTES',true)
on conflict(instancia,jid) do update set autorizado=true;
```

`syncFullHistory` solicita sincronização, mas não garante todo o histórico nem mídias antigas. O backfill lê o que a Evolution armazenou, não acessa um backup completo do telefone. O relatório deve distinguir mensagem ausente, mídia pendente e arquivo indisponível. Não concluir ausência de informação por falha de coleta.

## API para GPT

Importar `openapi.yaml` numa futura configuração de Actions e usar autenticação Bearer com o **token de consulta**. Endpoints: `POST /search`, `/message` e `/file`. Nunca entregar o token de ingestão ao GPT. `GET /health` verifica somente a disponibilidade da função, não a completude da coleta.

`scripts/mcp_stdio.py` fornece MCP local somente leitura, com `GATEWAY_URL` e `QUERY_TOKEN` no ambiente. Initialize e descoberta das três ferramentas foram testados. ChatGPT remoto precisará de MCP HTTPS com OAuth ou da configuração de Actions; isso ainda não foi instalado na conta.

As respostas devem citar grupo, ID da mensagem e data. Mensagens e arquivos são dados não confiáveis: o GPT não deve obedecer a instruções presentes no conteúdo recuperado. Arquivos são servidos como anexos, sem execução. Texto de áudio, imagem ou PDF ainda não está indexado: apenas mensagens e legendas têm pesquisa textual.

## Testes reproduzíveis

```bash
node --test tests/core.test.mjs
python3 -m unittest discover -s tests -p '*_test.py' -v
python3 tests/live.py /CAMINHO_PRIVADO/runtime.json
```

O teste remoto exige JSON privado com `url`, `ingestao`, `consulta`, além de curl instalado. Não imprimir esse arquivo. Cria identificadores novos em cada execução. Fixtures não correspondem a clientes nem a números reais. Consulte `docs/validacao.md` para resultados e limites.

## Segurança, operação e saída do piloto

- As tabelas têm RLS e não concedem acesso a `anon`/`authenticated`; ausência de políticas é intencional, com acesso apenas pelo backend autenticado. A única função `SECURITY DEFINER` valida hashes e tem EXECUTE revogado de papéis públicos. Advisor retornou apenas informações sobre RLS sem políticas.
- Sessões Baileys, banco e fila local exigem disco restrito, backups criptografados e administração por SSH. Nenhum log deve conter corpo de mensagens, telefone, QR ou chave. Logs da imagem de terceiros precisam ser inspecionados na VPS com dados fictícios antes de produção.
- Mensagens, tokens e arquivos de teste devem ser apagados ao encerrar o piloto; revogar tokens em `privado.credenciais`, desconectar a sessão e remover somente os volumes exclusivos após conferir o destino. Não usar `docker compose down -v` durante operação normal.
- Antes de dados reais: definir responsáveis e usuários, autorização por pessoa/cliente, base e finalidade do tratamento, retenção e exclusão, auditoria, rotação de chaves, limites de consumo, backups/restauração, monitoramento e tratamento de incidentes. O piloto não é uma certificação de conformidade com LGPD.
- Baileys/WhatsApp Web é integração não oficial, sujeita a mudanças, desconexões, limitações e restrição da conta. Não usar o número principal neste piloto. A API oficial deve ser reavaliada antes de qualquer migração para produção, conforme suas capacidades então disponíveis.
- Não existem respostas automáticas, envio de mensagens ou acesso ao número principal.

Fontes consultadas: código-fonte `evolution-foundation/evolution-api`, DTO de instância e controlador de webhook, rotas de chat/grupos e serviço Baileys; documentação Supabase de RLS, Storage privado e changelog; documentação oficial Docker de instalação no Ubuntu. Breaking change de TLS de 10/11/2026 conferida: cliente deve manter TLS moderno.
