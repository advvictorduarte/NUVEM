# Validação — 29/10/2026

Escopo: exclusivamente o projeto `whatsapp-gpt-piloto` (`lynpyfheouailjwqsvxl`) e arquivos novos em `whatsapp-piloto/`. Nenhuma escrita foi feita no Supabase `monitoramento-prazos`. Nenhum número WhatsApp foi conectado e nenhuma conversa real foi usada nos testes.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Normalização de texto e origem, histórico em lista, descarte de conversa pessoal | Aprovado localmente |
| Metadados de áudio, imagem, documento e vídeo | Aprovado localmente |
| Descarte de visualização única; marcação de exclusão | Aprovado localmente |
| Bloqueio de token ausente, escopo incorreto e instância principal | Aprovado localmente e na API implantada |
| JSON inválido e falha de backend sem vazamento de erro | Aprovado localmente |
| Relay: lista vazia, remoção de segredos, instância, fila persistente e retry | 5 testes aprovados |
| Conjunto de testes JavaScript | 9 testes aprovados |
| API implantada: conjunto de verificações remotas | 23 verificações aprovadas |
| Supabase: gravação somente no grupo autorizado | Aprovado com fixtures inventadas |
| Reenvio do mesmo evento | Marcado duplicado, sem segunda mensagem |
| Busca textual com ID, grupo, participante e data | Aprovado |
| Evento `messages.set` | Armazenado; evento simulado, sem prova de histórico real |
| PDF, imagem e áudio gerados para teste | Upload privado, download assinado e SHA-256 íntegro |
| URL pública sem assinatura dos mesmos anexos | Acesso negado |
| Papéis `anon` e `authenticated` | Zero concessões sobre tabelas do piloto; EXECUTE negado nas três funções |
| Storage | Bucket privado, limite de 20 MiB |
| Advisor de segurança | Apenas 9 avisos informativos de RLS sem políticas; bloqueio intencional do acesso direto |
| Metadados das quatro imagens no Docker Hub | Tags encontradas e digests fixados; pull/execução ainda não realizados |
| YAML Compose/OpenAPI e sintaxe Python/Bash | Válidos nas verificações locais |
| MCP stdio | Initialize e tools/list aprovados; chamadas por MCP e conexão ao ChatGPT não validadas |

O primeiro teste remoto foi concluído com fixtures fixas. Uma execução concorrente encontrou evento já entregue e revelou uma ambiguidade na asserção do teste, não uma falha de gravação. O teste passou a gerar IDs por execução e foi concluído novamente. Um teste SQL adicional de gravação sob `service_role` também passou. Somente mensagens e arquivos fictícios permanecem no projeto para inspeção.

## Limitações da validação

Não existe Docker/daemon nem VPS disponível neste ambiente. Não foi validado o pull das imagens, o boot dos contêineres ou o contrato HTTP da versão instalada da Evolution. Os endpoints e campos foram conferidos no código-fonte do fornecedor; são hipóteses de integração até o ensaio real na VPS. Não há captura ativa de WhatsApp.

O PDF de uma primeira fixture verificava transporte de bytes com cabeçalho PDF; a execução seguinte usa PDF sintaticamente completo gerado pelo teste. A imagem é PNG de 1 pixel e o áudio é WAV de silêncio. Não foram testados OCR, transcrição nem compreensão dos anexos.

Banco e API usam o plano gratuito conforme cotação de criação. Não foram ativados modelos pagos, embeddings, transcrição ou OCR. Região do banco: São Paulo; execução de Edge Functions pode ocorrer em outras regiões. Antes de tratar dados reais, avaliar os fluxos e as condições de proteção de dados dos fornecedores.

## Critério de aceite que ainda depende da VPS

Conectar conta secundária vazia; autorizar grupo fictício; comparar IDs de mensagens anteriores e posteriores; baixar anexos pelo endpoint real da Evolution; testar reconexão, restart, replay de histórico e falta de rede; verificar logs sem dados sensíveis, webhook persistido, contagens e lacunas. Só depois iniciar a etapa de integração com GPT e avaliar produção.
