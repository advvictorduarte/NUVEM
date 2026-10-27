# A parte que roda na nuvem

Montado em 27/10/2026. Aqui fica o que roda **sem o computador do escritório ligado**, e o que ainda não roda.

## Por que o banco coleta, e não uma Edge Function

A Fase 1 provou que o DJEN bloqueia por país. Ao montar a nuvem, a primeira tentativa foi uma Edge Function do Supabase, com o projeto na região São Paulo. **Levou 403.**

O motivo não era a região do projeto: **Edge Functions rodam na borda mais próxima de quem chama**. A chamada partiu dos Estados Unidos, a função rodou em Ashburn (Virgínia) e o CloudFront recusou.

O banco é diferente: o Postgres fica fisicamente na região escolhida. Medido de dentro dele:

```
saída: 15.229.216.40 · ec2-...sa-east-1.compute.amazonaws.com · São Paulo · BR
DJEN:  HTTP 200
```

Por isso **a coleta é feita pelo próprio banco**, com a extensão `http`. Se alguém no futuro for refazer isso como Edge Function, vai esbarrar no mesmo 403 — e a causa não é óbvia.

## O que está no ar

| Peça | Onde | Quando |
| --- | --- | --- |
| Coleta do DJEN | função `coletar_monitoramentos()` no banco | `pg_cron`, 12:00 UTC = 09:00 de Brasília |
| Projeto | Supabase `monitoramento-prazos`, ref `udcbqdzpofnbcvqemwxv`, `sa-east-1` | — |
| Tabelas | `publicacoes`, `execucoes_coleta`, `monitoramentos`, `arquivos_sistema` | — |
| Migrações | `supabase/migrations/` | versionadas |

Garantias verificadas na primeira execução real:

- **Idempotente.** Rodar duas vezes no mesmo dia: 0 novos, 8 atualizados.
- **Integridade.** O total recebido é conferido contra o `count` que a API declara; divergência marca a execução como incompleta, com o motivo.
- **Erro nunca vira ausência.** Falha de rede, HTTP diferente de 200 ou resposta que não é JSON gravam `completa = false` e o erro em `execucoes_coleta`.
- **Sem dado exposto.** RLS ligado e sem política em `publicacoes`, `execucoes_coleta` e `monitoramentos`. A única tabela de leitura pública é `arquivos_sistema`, que guarda **código**, nunca dado de cliente.

## O que falta, e depende do advogado

A tarefa agendada **"Relatório diário de prazos DJEN (Supabase)"** (09:15) existe e está ativa, mas **nasce sem os conectores Supabase e Gmail**. A ferramenta de criação recusou passá-los: só podem ser concedidos pelo titular da conta.

Teste disparado em 27/10/2026 às 02:06 confirmou: a sessão sobe sem as ferramentas `mcp__Supabase__*` e `mcp__Gmail__*`. Os conectores aparecem ligados na conta, mas com `enabledInChat: false`.

**Para destravar:** no claude.ai, habilitar os conectores **Supabase** e **Gmail** nessa rotina.

O teste serviu para uma coisa boa: a rotina falhou do jeito certo. Não chamou o DJEN, não inventou alternativa e avisou explicitamente que **não se pode concluir que não houve publicações**.

## Como a rotina monta o relatório

1. Lê `execucoes_coleta` para saber se a coleta do dia foi completa.
2. Lê as publicações do período e grava num JSON no formato do DJEN.
3. Baixa `gerar_relatorio.py` da tabela `arquivos_sistema` (gzip + base64) e executa.
4. Envia por e-mail com os dois anexos, e também no chat.
5. Se a coleta não foi completa, passa `--coleta-incompleta`, e o relatório sai com aviso vermelho no topo.

O gerador é um arquivo único montado a partir do pacote `coletor` por `scripts/monta_gerador.py`. **A fonte da verdade é o pacote**: alterar lá, rodar o script, e regravar em `arquivos_sistema`.
