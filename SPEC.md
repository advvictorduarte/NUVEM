# Especificação: busca e monitoramento processual próprio

Data da versão: 26/10/2026. Origem: análise do conector Tramitação Inteligente (pelas descrições das ferramentas) e da documentação pública de Jusbrasil Soluções (Digesto), Judit e Escavador.

## 1. Objetivo
Cobrir, sem contratar API paga, a parte do que o Tramitação Inteligente faz que importa ao escritório: intimações e prazos a partir do DJEN, movimentações pelo DataJud, classificação do ato e contagem de prazo por IA, agenda e alertas.

Fora do escopo desta versão: detecção de nova distribuição antes da intimação, download de autos e petição inicial em PDF, processos em segredo de justiça, citações e intimações pessoais pelo Domicílio Judicial Eletrônico.

## 2. Fontes e o que cada função consegue

| Função | Fonte sem contrato | Cobre? | Observação |
| --- | --- | --- | --- |
| Intimações e prazos pela OAB | DJEN (comunica.pje.jus.br) | Sim | Busca por tribunal, órgão, datas, número do processo, parte, advogado e OAB. Desde 27/01/2025 o DJEN substitui os outros meios de intimação não pessoal no PJe, JPe, SIAP e SISCOM, e o prazo conta da publicação nele |
| Movimentações de processos conhecidos | DataJud (API pública do CNJ) | Sim, com ressalvas | Capa e movimentos por número CNJ. Chave pública no cabeçalho `Authorization: APIKey`, que o CNJ pode trocar. Sem documentos e sem processos sigilosos |
| Agenda, prazos e sugestão de ato | Banco próprio e IA | Sim | É o que o projeto agrega |
| Citações e intimações pessoais | Domicílio Judicial Eletrônico | Não | Exige credencial do advogado |
| Nova distribuição antes da intimação | Nenhuma fonte pública equivalente | Não | Diferencial das APIs pagas |
| Autos e petição inicial | Sistema de cada tribunal | Não | Exige login ou certificado |
| Segredo de justiça | Nenhuma | Não | O DJEN omite partes e conteúdo |

Endpoint do DJEN, conforme a automação diária que o advogado já usa (ver seção 9):

`GET https://comunicaapi.pje.jus.br/api/v1/comunicacao?pagina=1&itensPorPagina=100&numeroOab=<número>&ufOab=<UF>&dataDisponibilizacaoInicio=AAAA-MM-DD&dataDisponibilizacaoFim=AAAA-MM-DD`

Resposta em JSON com a lista em `items`. Campos usados pela automação: `texto`, `siglaTribunal`, `data_disponibilizacao`, `numeroprocessocommascara` e `destinatarios` (nomes). **Ainda não validado pelo projeto:** lista completa de campos, limite de requisições, paginação além da primeira página, necessidade de chave e se a chamada funciona fora do navegador (a automação atual busca por dentro de uma página aberta no Chrome). A Fase 1 resolve isso.

## 3. O que o Tramitação Inteligente organiza (referência de produto)

| Módulo | Entidades e campos principais | Função |
| --- | --- | --- |
| Processos | Tipo (judicial, administrativo, outro); número CNJ de 20 dígitos; tribunal (94 siglas); comarca, juízo, ajuizamento, valor da causa; status; desfecho nos marcos do CNJ; etiquetas; clientes com polo | Lista com filtros; escrita em lote de até 100; campo de última atualização que considera andamento e documento |
| Movimentações e documentos | Andamentos; documentos do tribunal; marcadores de coleta | Feed por intervalo (máximo 90 dias); linha do tempo; leitura de texto em janelas |
| Publicações | Vêm do feed do CNJ (DJEN); status não lida, tratada, arquivada; resumo e sugestões de atividade por IA | Transforma sugestão em prazo com data contada em dias úteis e feriados |
| Atividades e prazos | Tipos: tarefa, evento, reunião, despacho, audiência, prazo, perícia; início, dias, contagem, suspensão no recesso de 20/12 a 20/01; responsáveis com papel | Agenda por processo, cliente e etiqueta |
| Clientes | Cliente, contato, colaborador, parte; CPF/CNPJ; representantes; e-mail de entrada | Busca e lote |
| Workflows | Sequência de tarefas com prazo contado de uma data de referência ou da conclusão da anterior | Inicia em processo ou cliente; confirmação em duas etapas; desfazer |

Padrões de desenho a copiar:
- Escrita em massa em lote, com chave de idempotência.
- Ação em massa com confirmação e contagem esperada.
- Coleta diária consolidada; a resposta diz até que dia os dados estão completos.
- Paginação por cursor e total na primeira página.

## 4. O que as APIs pagas têm em comum
- Consulta pontual (síncrona) separada do monitoramento (recorrente).
- Monitoramento é um recurso com ID, estado (criado, atualizando, atualizado, pausado, deletado) e histórico.
- Evento por webhook, com consulta posterior do histórico para recuperar falhas.
- Andamentos normalizados em tipos padronizados.
- Jusbrasil Soluções: limite de 120 requisições por minuto e 5.000 por dia; anexos por URL válida por 90 dias.
- Judit: monitoramento do DJEN roda toda madrugada e captura o dia anterior, um evento por publicação.
- Escavador: solicitação de atualização sob demanda com consulta de status; token para validar a origem do callback.

## 5. Arquitetura

Fontes (DJEN, DataJud, e o Tramitação só para comparar) alimentam um **coletor diário** (rotina agendada). O coletor busca, deduplica e grava nas tabelas. A **IA** lê a publicação, identifica o ato e propõe o prazo. As saídas são **alerta**, **agenda** e **painel**.

## 6. Modelo de dados (sugestão)

| Tabela | Campos principais | Alimentada por |
| --- | --- | --- |
| `publicacoes` | ID do DJEN (único), número CNJ, tribunal, órgão, tipo de comunicação, tipo de documento, data de disponibilização, texto integral, partes, advogados com OAB, hash, status | DJEN |
| `processos` | Número CNJ (único), tribunal, grau, classe, assuntos, órgão julgador, ajuizamento, nível de sigilo, cliente, etiquetas, situação, última atualização | DataJud e cadastro |
| `movimentacoes` | Processo, data e hora, código e nome do movimento, complementos, órgão, hash | DataJud |
| `prazos` | Publicação e processo de origem, tipo, título, início, dias, contagem (úteis ou corridos), suspensão no recesso, data fatal, responsável, situação, `confirmado_por_advogado` | IA, revisado pelo advogado |
| `monitoramentos` | Tipo (OAB ou CNJ), chave, estado, última execução | Cadastro |
| `execucoes_coleta` | Fonte, início, fim, quantidade de novos, erro | Coletor |
| `alertas` | Prazo, canal, enviado em | Coletor e IA |

**Implementado em 27/10/2026** (migrações em `supabase/migrations/`): `publicacoes`, `execucoes_coleta` e `monitoramentos`. As demais tabelas seguem como previsão.

Ajustes que os dados reais impuseram ao modelo:
- **`link` identifica o ato.** O DJEN emite uma publicação por intimado: o mesmo despacho vira 2 ou 3 registros, com `id` e `hash` diferentes, mas o mesmo `link`. Em 26/10/2026, 8 publicações eram 5 atos. A deduplicação por `id` não resolve isso; agrupar por `link` resolve.
- **Campos de cancelamento** (`ativo`, `situacao`, `data_cancelamento`, `motivo_cancelamento`) existem e são regravados a cada coleta, para capturar anulação posterior.
- **`visto_em` e `atualizado_em`** separados: um diz quando a API ainda trazia o registro, o outro quando algo de fato mudou.
- RLS ligado e sem política em todas as tabelas: só a chave de serviço lê.

Decisões:
- Deduplicação por ID e hash.
- `execucoes_coleta` guarda até que dia a coleta está completa.
- `confirmado_por_advogado` impede alerta definitivo de prazo não conferido.

## 7. Roadmap
1. **Testar as fontes.** Ver `FASE-1.md`. Saída: aparecem as intimações recentes que o advogado já conhece.
2. **Coletor e banco.** Tabelas no Supabase e rotina diária. Saída: roda sem duplicar e sem pular dia.
3. **IA de prazos.** Classificar e propor prazo, comparando com as sugestões do Tramitação nas mesmas publicações. Saída: amostra conferida bate.
4. **Alertas e painel.** Roda em paralelo ao Tramitação por um período, sem divergência relevante.
5. **Ampliações.** Monitorar CNJs da carteira pelo DataJud. Avaliar API paga só se faltarem distribuição antecipada ou autos.

## 8. Limites e cuidados
- O prazo é do advogado; a IA propõe e ele confirma. A publicação no DJEN costuma sair no primeiro dia útil depois da expedição no PJe.
- LGPD e sigilo: acesso restrito ao banco e backup. Não contornar o sigilo do DJEN.
- Credenciais de tribunais e Domicílio Judicial ficam fora do escopo.
- Chave do DataJud em variável de ambiente.
- Prever log de falha e alerta quando a coleta do dia não rodar.
- Sem raspagem de sites de tribunais sem ler os termos de uso de cada um.

## 9. Referência: automação diária atual do escritório

O advogado já tem uma tarefa agendada ("Relatório diário de prazos DJEN") que roda todo dia às 09:00. Ela é a base do projeto e a Fase 2 deve reproduzir, no mínimo, o que ela faz.

**Fluxo atual:** abre o Chrome, chama o endpoint do DJEN pela OAB com data de ontem e hoje (fuso America/Sao_Paulo), lê o JSON dentro da página (a leitura de texto da página trunca JSON grande), classifica cada item, gera um PDF em cards (reportlab) e uma planilha Excel (openpyxl), salva na pasta de prazos do computador e envia os dois pelo chat.

**Regras de classificação atuais:**

| Situação do item | Prioridade | Tratamento |
| --- | --- | --- |
| Campo `texto` vazio ou ausente | SIGILO/ATENÇÃO | Sem prazo; "sem teor disponível na API pública, possível sigilo" |
| Texto com "em N dias" ou "prazo de N dias", tribunal que não é TRT nem TST | URGENTE (N até 5), ALTA (6 a 15), MÉDIA (acima de 15) | Dias úteis: publicação = 1º dia útil após a disponibilização; início = 1º dia útil após a publicação; prazo final = N dias úteis do início; prazo do escritório = 3 dias úteis antes do final; feriados não considerados |
| Texto com N dias, tribunal TRT ou TST | MÉDIA | Prazo não calculado; "requer conferência manual" |
| Sem dias, mas com "audiência" e data dd/mm/aaaa | MÉDIA | Prazo fixo = a data |
| Mero andamento (arquivamento, sem saldo, nomeação de perito, lista de distribuição, distribuído) | BAIXA | Sem prazo |
| Qualquer outro | MÉDIA | "nenhum prazo identificado automaticamente" |

Cores do relatório: SIGILO/ATENÇÃO roxo #7030A0, URGENTE vermelho #C00000, ALTA laranja #E36C09, MÉDIA azul-acinzentado #8EA9DB, BAIXA verde #A9D18E. Colunas da planilha: Prioridade, Processo, Cliente/Parte, Tribunal/Órgão, Tipo de ato, Teor, Disponibilização, Publicação, Início do prazo, Dias úteis do prazo, Prazo final, Prazo do escritório, Regra aplicada, Sugestão de medida, com datas calculadas por fórmula `WORKDAY`.

**Pontos a revisar ao migrar para o sistema próprio:**

1. **Justiça do Trabalho — decidido em 27/10/2026: mantida a regra atual.** O advogado determinou que valem, por enquanto, as regras da automação agendada como estão: **TRT e TST seguem sem prazo calculado automaticamente**, marcados para conferência manual. Registre-se, para quando o ponto voltar à mesa, que desde a Lei 13.467/2017 o art. 775 da CLT manda contar prazo trabalhista em dias úteis, e que **72% das publicações do escritório são trabalhistas** (`docs/fase1-relatorio.md`, seção 1.5) — ou seja, é essa a fatia que segue sem prazo calculado. Regras vigentes em `docs/regras-classificacao.md`.
2. **Feriados e recesso.** Hoje não há feriado forense nem o recesso de 20/12 a 20/01. Precisa de calendário (nacional, estadual do RJ, municipal e feriados forenses por tribunal).
3. **Busca do número de dias.** O padrão "em N dias" ou "prazo de N dias" não pega o formato por extenso com número entre parênteses ("15 (quinze) dias") nem prazos citados por artigo. Deve ser trocado por leitura da IA com revisão, mantendo o regex só como conferência.
4. **Janela de dois dias.** A consulta pega ontem e hoje. Se a rotina falhar um dia, perde-se publicação. O sistema próprio deve consultar desde a última execução bem-sucedida (tabela `execucoes_coleta`).
5. **Sem histórico.** Cada relatório é um arquivo novo. No sistema próprio, o mesmo item não pode reaparecer como novo (deduplicação) e o estado (tratada, prazo cumprido) precisa persistir.
6. **Dependência do Chrome.** A coleta roda dentro do navegador. Se a API do CNJ aceitar chamada direta, o coletor deixa de depender do Chrome e da extensão; isso precisa ser testado.
7. **Sigilo.** O texto vazio é tratado como possível sigilo, o que é uma suposição. Pode ser falha da API; marcar como "a verificar".

## 10. Nuvem — resolvido em 27/10/2026

**O coletor já roda na nuvem, sem depender do computador do advogado.** Projeto Supabase `monitoramento-prazos`, região **São Paulo (sa-east-1)**, com `pg_cron` disparando a coleta todo dia às 12:00 UTC (09:00 de Brasília).

O ponto que travava tudo foi resolvido por medição, e com uma surpresa:

- **Edge Function não serve para chamar o DJEN.** Elas rodam na borda mais próxima de quem chama, não na região do projeto. Chamada a partir dos EUA, a função saiu de Ashburn (Virgínia) e levou o 403 de bloqueio por país.
- **O banco serve.** O Postgres fica fisicamente na região escolhida. Dele, a saída é `sa-east-1`, São Paulo, country BR — e o DJEN respondeu **HTTP 200**. Por isso a coleta é feita pelo próprio banco, com a extensão `http`, e não por Edge Function.

Verificado na prática: coleta completa, 8 publicações; segunda execução no mesmo dia gerou 0 novos e 8 atualizados (idempotente); a contagem recebida é conferida contra o `count` que a API declara, e divergência marca a execução como incompleta.

**Falta:** a geração e a entrega do PDF e da planilha a partir do banco. É a última peça para o advogado não precisar de computador ligado nem de comando nenhum.

A direção original, mantida como registro:

- **Banco:** Supabase (a confirmar). O advogado já tem o conector do Supabase no Claude.
- **Coletor:** função do Supabase (Edge Function) chamando DJEN e DataJud direto, com agendamento diário no próprio Supabase, sem depender do computador do advogado nem do Chrome.
- **Classificação e relatório:** duas opções. (a) Manter a tarefa agendada do Claude lendo as publicações novas no banco; sem custo de API à parte. (b) IA dentro da função, o que exige chave de API da Anthropic, cobrada à parte da assinatura.
- **Riscos a testar:** bloqueio por região (sites do governo às vezes recusam acesso de fora do Brasil; o Supabase permite escolher região, inclusive São Paulo, a confirmar) e se a API do DJEN aceita chamada direta sem navegador.
- **Teste sem o Chrome**, a rodar no computador do advogado (PowerShell):

```
Invoke-RestMethod "https://comunicaapi.pje.jus.br/api/v1/comunicacao?pagina=1&itensPorPagina=1&numeroOab=<OAB_NUMERO>&ufOab=<OAB_UF>&dataDisponibilizacaoInicio=AAAA-MM-DD&dataDisponibilizacaoFim=AAAA-MM-DD"
```

Resposta com `items` = chamada direta funciona. Erro 403, bloqueio ou página de verificação = registrar a mensagem exata no relatório da Fase 1.

## 11. Fontes consultadas
- Jusbrasil Soluções, documentação da API: https://api.jusbrasil.com.br/docs/index.html
- Judit, monitoramento do DJEN: https://docs.judit.io/tracking/tracking-communication
- Escavador, documentação da API: https://api.escavador.com/v2/docs/index
- CNJ, API pública do DataJud: https://www.cnj.jus.br/sistemas/datajud/api-publica/
- TJMG, protocolo DJEN e Domicílio Judicial Eletrônico (PDF, ago/2025)
