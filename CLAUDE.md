# Projeto: monitoramento processual próprio do escritório

Sistema interno para acompanhar intimações, prazos e movimentações dos processos do escritório sem depender de API paga. Especificação completa em `SPEC.md`. A tarefa atual está em `FASE-1.md`. O escritório já tem uma automação diária de prazos do DJEN (descrita na seção 9 do `SPEC.md`); o sistema próprio parte dela, não a ignora. O texto do prompt dela está em `REFERENCIA-AUTOMACAO-ATUAL.md`. Ordem combinada: primeiro Code (Fase 1 em diante); nuvem só depois, sem pular etapa.

## Idioma
Responder, comentar e documentar em português do Brasil. Nomes de tabelas e colunas em português, sem acento, em minúsculas com sublinhado (`publicacoes`, `data_fatal`).

## Fontes permitidas
- DJEN (Diário de Justiça Eletrônico Nacional), pela API do CNJ.
- DataJud, API pública do CNJ.
- Conector Tramitação Inteligente, somente como comparação, nunca como dependência.

Não raspar sites de tribunais nem de agregadores (Jusbrasil e similares) sem aprovação expressa do advogado, caso a caso.

## Regras que não podem ser quebradas
1. **O prazo é do advogado.** Todo prazo gerado pela IA nasce com `confirmado_por_advogado = false` e não dispara alerta definitivo até ser confirmado.
2. **Nunca afirmar "sem novidades".** Antes de dizer que não houve publicação ou movimentação, consultar `execucoes_coleta` e informar até que dia a coleta está completa.
3. **Não inventar endpoint nem parâmetro.** Todo endpoint só vira código depois de testado e de o resultado real ser registrado em `docs/`. O que não foi validado é marcado como "não validado".
4. **Segredos fora do código.** Chave do DataJud e credenciais ficam em variáveis de ambiente (`.env` fora do git). O CNJ pode trocar a chave do DataJud a qualquer momento.
5. **Sem credenciais de clientes.** Não guardar senha do gov.br, certificado digital nem login de tribunal no banco ou no repositório.
6. **Sigilo.** O DJEN omite partes e conteúdo de processo sigiloso. O sistema não tenta contornar isso.
7. **Dados de clientes não vão para log.** Logs registram IDs, contagens e erros, nunca o texto integral das publicações nem nomes de partes.
8. **Contagem de prazo.** Publicação = 1º dia útil após a disponibilização (campo `data_disponibilizacao`); início do prazo = 1º dia útil após a publicação. Qualquer dúvida de contagem vai para o advogado, não para suposição.
   - **Decisão do advogado em 27/10/2026:** valem, por enquanto, as regras da automação agendada atual (`REFERENCIA-AUTOMACAO-ATUAL.md`), tal como estão. Em consequência, **TRT e TST não têm prazo calculado automaticamente** — o item é marcado para conferência manual. A redação anterior desta regra mandava calcular prazo trabalhista em dias úteis (art. 775 da CLT após a Lei 13.467/2017) e está suspensa, não revogada: o ponto volta à mesa quando o advogado quiser. Ver `docs/regras-classificacao.md`.
   - Feriados forenses e o recesso de 20/12 a 20/01 **não** entram no cálculo hoje, porque a automação atual não os considera. É a limitação nº 2 da seção 9 do `SPEC.md`.
9. **Citação não verificada é sinalizada.** Número de processo ou julgado que não puder ser confirmado em fonte oficial é marcado como não confirmado e nunca entra como certo.

## Forma de trabalhar
- Migrações do banco versionadas em `supabase/migrations/`, uma por mudança.
- Teste automatizado para a contagem de prazo (dias úteis, feriados, recesso de 20/12 a 20/01) e para a deduplicação.
- Coleta idempotente: rodar duas vezes no mesmo dia não pode duplicar registro.
- Antes de mudar o modelo de dados, atualizar `SPEC.md`.
- Banco previsto: Supabase. A confirmar com o advogado antes da primeira migração.

## Dados do escritório usados como parâmetro
- OAB monitorada: variáveis `OAB_NUMERO` e `OAB_UF` no `.env`.
- Outras OABs do escritório entram na tabela `monitoramentos`.
