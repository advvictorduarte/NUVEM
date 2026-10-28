# Teste de alternativas sem Supabase — 28/10/2026

Código-base: commit 019c69beab57d365d3af8bc9e558e977170d53da.
Diagnóstico isolado na branch teste/sem-supabase-2026-10-28. Sem alteração da main ou da rotina diária.

## Resultados observados

| Alternativa | Resultado |
| --- | --- |
| Obter o código do repositório | Clone concluído e HEAD confirmado. Leitura pelo conector GitHub também funcionou. |
| Executar Python localmente | Funcionou. reportlab, openpyxl e Pillow disponíveis. |
| Testes do projeto | 25 testes passaram localmente e no GitHub Actions. |
| Gerar relatórios a partir de JSON sem banco | Funcionou com testes/exemplo-djen.json: PDF abriu com 2 páginas; XLSX abriu com abas Leia-me e Prazos e 6 registros mais cabeçalho. |
| Coletar pelo executor padrão do GitHub Actions | Falhou por bloqueio de país do DJEN. Executor observado: Azure centralus. |
| Coletar em computador/servidor no Brasil | Não testado: nenhum equipamento ou servidor brasileiro foi disponibilizado para execução. |
| Envio automático por e-mail sem Supabase | Não testado neste diagnóstico. Os módulos locais inspecionados não implementam esse envio. |

Execução remota e logs: https://github.com/advvictorduarte/NUVEM/actions/runs/40745110147

Erro retornado pelo coletor no executor GitHub:
“A API do DJEN recusou este computador por país (bloqueio do CloudFront). A coleta precisa rodar de uma rede brasileira.”

O diagnóstico remoto consultou somente uma página com um item, sem imprimir teor ou nomes de partes, sem salvar publicações no repositório e sem alegar coleta completa. A API do DJEN não foi chamada do contêiner local.

## Limites para uso diário

A geração por JSON foi comprovada tecnicamente com dados de exemplo. Não constitui relatório das publicações do dia nem comprovação de coleta real.

O caminho disponível para dispensar totalmente o Supabase é executar a coleta em rede brasileira e manter publicações e estado da coleta em arquivos locais protegidos. Esse caminho ainda depende de teste no equipamento escolhido.

O importador principal.py --json assume coleta completa a partir do arquivo recebido. O gerador gerar_relatorio.py exige o parâmetro --coleta-incompleta quando não há comprovação de completude. Antes de automatizar uma exportação, o estado da coleta deve ser validado explicitamente; quantidade zero sem essa confirmação nunca significa ausência de publicações.

O repositório é público: publicações, partes, credenciais e arquivos reais do escritório não devem ser adicionados a ele. O diagnóstico contém apenas código, contagens e erros.

Prazos permanecem sugestões sujeitas à validação do advogado. TRT e TST permanecem sem prazo calculado automaticamente.
