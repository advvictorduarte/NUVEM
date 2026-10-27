# Regras vigentes de classificação e prazo

**Decisão do advogado em 27/10/2026:** valem, por enquanto, as regras da automação agendada atual, tal como estão hoje. Este documento é a transcrição delas em forma implementável, já corrigida pelos nomes de campo reais validados na Fase 1.

Fonte da regra: `REFERENCIA-AUTOMACAO-ATUAL.md`. Fonte dos nomes de campo: `docs/fase1-relatorio.md`, seção 1.4 (resposta real da API, conferida em 26/10/2026).

Quem implementar a Fase 2 segue **este** documento. Onde ele e o `SPEC.md` divergirem, vale este, porque é o que o advogado decidiu.

---

## 1. Coleta

| Item | Regra vigente |
| --- | --- |
| Endpoint | `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao` |
| Parâmetros | `pagina`, `itensPorPagina=100`, `numeroOab`, `ufOab`, `dataDisponibilizacaoInicio`, `dataDisponibilizacaoFim` |
| Janela | de **ontem** até **hoje**, fuso `America/Sao_Paulo` |
| Chamada | **direta, sem navegador** — validado na Fase 1, 0,8 s. O Chrome deixa de ser necessário; exige apenas IP brasileiro |
| Paginação | enquanto a página devolver 100 itens, buscar a próxima. Conferir o total contra o campo `count` do envelope |

**Erro nunca vira "nenhuma publicação".** O passo 8 da automação manda gerar o relatório mesmo com zero publicações, dizendo "nenhuma publicação encontrada no período". Isso só pode ser dito quando a consulta **respondeu**. Se a chamada falhou (erro de rede, HTTP diferente de 200, resposta que não é JSON), o relatório diz que **a coleta falhou** e qual foi o erro — nunca "nenhuma publicação". É o passo 9 da automação e a regra 2 do `CLAUDE.md`.

## 2. Campos usados

Nomes conferidos contra a resposta real:

| Uso | Campo |
| --- | --- |
| Teor da publicação | `texto` |
| Tribunal | `siglaTribunal` |
| Data de disponibilização | `data_disponibilizacao` |
| Processo (exibição) | `numeroprocessocommascara` |
| Processo (consulta ao DataJud) | `numero_processo` |
| Cliente / partes | `destinatarios` |
| Advogados intimados | `destinatarioadvogados` |
| Órgão | `nomeOrgao` |
| Tipo de ato | `tipoComunicacao`, `tipoDocumento` |
| Classe | `nomeClasse` |
| Identificador | `id` |

Existe também um campo `datadisponibilizacao`, sem sublinhados, que **diverge** de `data_disponibilizacao` em todas as publicações observadas. **A contagem usa `data_disponibilizacao`**, que é o que a automação atual usa. O outro campo fica anotado como não esclarecido.

## 3. Classificação

Na ordem. A primeira regra que casar decide.

| # | Condição | Prioridade | Prazo |
| --- | --- | --- | --- |
| 1 | `texto` vazio ou ausente | **SIGILO/ATENÇÃO** | Não calculado. Observação: "sem teor disponível na API pública, possível sigilo" |
| 2 | `texto` casa `em N dias` ou `prazo de N dias` **e** `siglaTribunal` **não** começa com `TRT` nem é `TST` | **URGENTE** se N ≤ 5 · **ALTA** se 6 ≤ N ≤ 15 · **MÉDIA** se N > 15 | Calculado em dias úteis (seção 4) |
| 3 | `texto` casa `em N dias` ou `prazo de N dias` **e** o tribunal é `TRT*` ou `TST` | **MÉDIA** | **Não calculado.** Observação: "regra CLT — requer conferência manual" |
| 4 | `texto` menciona `audiência` e uma data `dd/mm/aaaa` | **MÉDIA** | Prazo fixo = essa data. Observação: "data fixa de audiência" |
| 5 | `texto` sugere mero andamento: `arquivamento`, `sem saldo`, `nomeação de perito`, `lista de distribuição`, `distribuído` | **BAIXA** | Sem prazo |
| 6 | Qualquer outro caso | **MÉDIA** | Observação: "nenhum prazo identificado automaticamente — requer leitura manual do teor" |

A regra 3 é a decisão de 27/10/2026. **Ela atinge 72% das publicações do escritório** (`docs/fase1-relatorio.md`, seção 1.5): essas seguem sem prazo calculado, por decisão, e dependem de conferência manual.

## 4. Contagem de prazo (regras 2 e 4 acima)

1. **Publicação** = 1º dia útil após `data_disponibilizacao`.
2. **Início do prazo** = 1º dia útil após a publicação.
3. **Prazo final** = N dias úteis contados do início.
4. **Prazo do escritório** = 3 dias úteis antes do prazo final.

Dia útil = segunda a sexta. **Feriados forenses e o recesso de 20/12 a 20/01 não entram**, porque a automação atual não os considera — é limitação conhecida e tem de aparecer no aviso do relatório.

Todo prazo nasce com `confirmado_por_advogado = false` (regra 1 do `CLAUDE.md`).

## 5. Cores

| Prioridade | Cor |
| --- | --- |
| SIGILO/ATENÇÃO | roxo `#7030A0` |
| URGENTE | vermelho `#C00000` |
| ALTA | laranja `#E36C09` |
| MÉDIA | azul-acinzentado `#8EA9DB` |
| BAIXA | verde `#A9D18E` |

## 6. Saídas

**PDF** (`reportlab`), nome `relatorio_prazos_AAAA-MM-DD.pdf`: título "Relatório Diário de Publicações e Prazos", nome e OAB do advogado, data, resumo numérico por prioridade, agrupado por prioridade nessa ordem, um card por publicação com processo, cliente/partes, tribunal/órgão, tipo de ato, teor resumido, datas de disponibilização/publicação/início, prazo final e prazo do escritório em vermelho, regra aplicada e sugestão de medida.

**Aviso obrigatório no PDF**, em itálico vermelho: classificação e prazos são gerados automaticamente por heurística de texto; exigem validação humana; **não consideram feriados forenses nem o recesso**; e **TRT e TST não têm prazo calculado**.

**Planilha** (`openpyxl`), nome `controle_prazos_AAAA-MM-DD.xlsx`: aba "Leia-me" com as mesmas limitações e aba de dados com as colunas — Prioridade, Processo, Cliente/Parte, Tribunal/Órgão, Tipo de ato, Teor, Disponibilização, Publicação, Início do prazo, Dias úteis do prazo, Prazo final, Prazo do escritório, Regra aplicada, Sugestão de medida. Datas como `datetime.date` reais, colunas calculadas por fórmula `WORKDAY`, preenchimento da coluna Prioridade nas cores acima.

**Entrega:** salvar na pasta de prazos do computador quando possível e, de qualquer forma, enviar os dois arquivos no chat.

---

## 7. Limitações aceitas por decisão, não por desconhecimento

Ficam valendo, e devem constar do aviso do relatório:

1. **TRT e TST sem prazo calculado** — 72% das publicações.
2. **Sem feriados forenses nem recesso** de 20/12 a 20/01.
3. **Busca do número de dias por expressão regular**, que não pega "15 (quinze) dias" nem prazo citado por artigo de lei.
4. **Janela de dois dias** — se a rotina falhar um dia, perde-se publicação.
5. **Sem histórico** — cada relatório é um arquivo novo; o mesmo item reaparece como novo.

## 8. Melhorias levantadas na Fase 1 e **não** adotadas

Ficam registradas aqui, sem entrar no código, até o advogado decidir uma a uma:

| Melhoria | Por que foi levantada |
| --- | --- |
| Reprocessar publicações já coletadas para detectar **cancelamento** | Os campos `ativo`, `status`, `data_cancelamento` e `motivo_cancelamento` existem na API. Publicação cancelada derruba o prazo que nasceu dela. Nenhum caso em 30 dias |
| Deduplicação por `id` e `hash` | Os dois campos vêm prontos; 159 publicações, 159 IDs únicos |
| Coletar desde a última execução bem-sucedida | Substitui a janela de dois dias e elimina a perda por falha de um dia |
| Calendário de feriados e recesso | Limitação nº 2 |
| Leitura do prazo por IA, com a expressão regular só como conferência | Limitação nº 3 |
| Contagem trabalhista em dias úteis (art. 775 da CLT) | Limitação nº 1 — **suspensa por decisão de 27/10/2026**, não revogada |
