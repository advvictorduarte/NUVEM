# Fase 1: testar as fontes

Objetivo: descobrir, com chamadas reais, o que o DJEN e o DataJud entregam, antes de escrever qualquer tabela. Ler `CLAUDE.md` e `SPEC.md` primeiro.

Resultado esperado: o arquivo `docs/fase1-relatorio.md` e um script de teste em `scripts/fase1/`. Nenhuma migração do banco nesta fase.

## Preparação
1. Criar `.env.example` com `OAB_NUMERO`, `OAB_UF` e `DATAJUD_API_KEY` (sem valores). O advogado cria o `.env` real e confirma os valores.
2. A chave pública do DataJud está na wiki do CNJ: https://datajud-wiki.cnj.jus.br/api-publica/acesso/. O CNJ pode trocá-la; nunca copiar a chave para o código.
3. Escolher a linguagem do script (Python ou Node) e avisar a escolha ao advogado.

## Teste A: DJEN
1. Partir do endpoint que a automação diária do advogado já usa (ver `SPEC.md`, seções 2 e 9):
   `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao` com `pagina`, `itensPorPagina` (a automação usa 100), `numeroOab`, `ufOab`, `dataDisponibilizacaoInicio` e `dataDisponibilizacaoFim`. Confirmar o que funciona e registrar o que for recusado.
2. **Testar a chamada direta, fora do navegador** (a automação atual busca por dentro de uma página no Chrome; a hipótese é que o Chrome só existe por causa do bloqueio de rede do ambiente das tarefas agendadas, e não porque a API exija navegador). O advogado roda no Windows; o teste em PowerShell está em `SPEC.md`, seção 10. Registrar se a chamada direta funciona, se exige cabeçalho, chave ou cadastro, e se há bloqueio por origem. Se não funcionar, registrar o erro exato e propor alternativa.
3. Buscar as comunicações da OAB (`OAB_NUMERO` / `OAB_UF`) dos últimos 30 dias, percorrendo todas as páginas.
4. Registrar no relatório:
   - parâmetros que funcionaram e os que foram recusados;
   - quantos itens vêm com `texto` vazio e se isso coincide com processo sigiloso (hoje a automação assume que sim);
   - se exige chave ou cadastro;
   - paginação (tamanho de página, como pedir a próxima);
   - limites de requisição observados;
   - lista de campos retornados, com exemplo (sem texto de cliente: mascarar nomes e CPFs no relatório);
   - tempo de resposta e comportamento em erro.
5. Comparar o resultado com os relatórios diários que a automação já gerou (PDF e planilha dos últimos dias). Anotar divergências em itens, campos e datas.

## Teste B: DataJud
1. Ler a wiki e confirmar o formato de endpoint por tribunal e de consulta.
2. Consultar uma lista de CNJs fornecida pelo advogado (usar poucos processos, de TRT-1, TJRJ, JEC e JEF).
3. Registrar no relatório, por tribunal: se o processo foi encontrado, campos de capa, quantidade e tipo de movimentos, e a data do último movimento comparada com o que o advogado vê no tribunal.
4. Anotar defasagem, processos não encontrados e comportamento com sigilo.

## Teste C: comparação com o Tramitação (opcional)
Para as mesmas publicações do período, comparar o que o conector Tramitação Inteligente mostra com o que o DJEN devolveu. Anotar o que falta de cada lado.

## Relatório `docs/fase1-relatorio.md`
Seções: resultado do Teste A, resultado do Teste B, comparação, decisões pendentes e riscos. Tudo que não foi testado fica marcado como "não validado".

## Critério de saída
- O DJEN devolve as intimações recentes que o advogado já conhece, pela OAB.
- O DataJud devolve movimentos de pelo menos um processo de cada tribunal testado, ou o relatório explica por que não.
- O advogado aprova o relatório antes de a Fase 2 começar.

## Fora desta fase
Banco, IA, alertas, painel, raspagem de sites e qualquer credencial de tribunal.
