# Captura automática: correção de 29/10/2026

O piloto local foi instalado e a Evolution conectou. Uma importação manual de grupo inicial entregou 337 mensagens ao Supabase; isso valida backfill, não valida webhook nem captura em tempo real. O usuário passou a enviar testes num segundo grupo chamado Teste, ainda fora das listas autorizadas.

Também havia um problema no código: a mesma thread entregava mensagens e baixava até 20 anexos sequenciais antes de voltar à fila. Cada download podia esperar 40 segundos; portanto, o comentário que dizia que mídias não bloqueavam texto estava incorreto.

Correção:

- Thread exclusiva para mensagens, acordada ao receber evento e com intervalo máximo de ociosidade de 1 segundo.
- Thread independente com dois downloads paralelos e lotes de dois itens; novos anexos recebem prioridade no backend, mantendo os antigos pendentes com retry.
- Suporte a SEND_MESSAGE além de MESSAGES_UPSERT, inclusive envios feitos pela API/Manager.
- Diagnóstico no /health com contagem de fila e instantes de último webhook e entrega ao Supabase, sem conteúdos ou chaves.
- Script `scripts/ativar_tempo_real.py --grupo JID` preserva os grupos já autorizados localmente, adiciona o grupo indicado, reaplica o webhook autenticado e verifica configuração persistida. A autorização correspondente no Supabase é obrigatória e independente.

Aplicação no computador:

```bash
git pull --ff-only
python3 scripts/ativar_tempo_real.py --grupo JID_DO_GRUPO_AUTORIZADO
sudo docker compose up -d --no-deps --build relay
```

Não precisa recriar a instância nem ler outro QR. O procedimento não envia mensagens. As mensagens anteriores que tenham sido descartadas por falta de autorização exigem backfill uma vez; as novas devem seguir pelo webhook automaticamente.

Validação local: 18 testes aprovados (10 JavaScript e 8 Python). O teste concorrente mantém um download bloqueado e comprova entrega de mensagem nova antes de liberá-lo; testes de configuração verificam manutenção da lista e ausência de token na saída. Ainda depende do ensaio no computador para confirmar o webhook da imagem 2.3.7 e a captura real.

O Evolution Manager é uma interface do fornecedor, separada da API de consulta. Captura no banco e renderização imediata na tela do Manager são verificações diferentes. Este projeto mantém base64 do webhook desativado; a exibição de anexos no Manager pode não funcionar mesmo quando os bytes estão guardados no bucket privado. Não habilitar captura irrestrita de mídia de toda a conta para contornar uma limitação visual.

Objetivo operacional: mensagens em poucos segundos quando os serviços e a rede estiverem disponíveis; fotos dependem de transferência. Não há garantia de latência zero ou disponibilidade contínua. O computador deve permanecer ligado e sem suspensão.
