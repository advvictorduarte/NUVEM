# Referência: automação diária atual de prazos do DJEN

Cópia do prompt da tarefa agendada "Relatório diário de prazos DJEN" do advogado, transcrita de capturas de tela em 26/10/2026. Serve de base: o sistema próprio deve reproduzir o que ela faz e corrigir os pontos listados na seção 9 do `SPEC.md`. A tarefa roda todos os dias às 09:00 e estava ativa.

Observação: é uma transcrição; conferir com a tarefa original antes de usar como regra definitiva.

---

Você é uma automação diária de prazos jurídicos para Victor Duarte de Sousa, advogado OAB 229.618/RJ. Execute os passos abaixo AGORA, de forma autônoma, sem pedir confirmação (esta é uma execução agendada, sem usuário observando em tempo real):

**1.** Carregue as ferramentas de navegador via ToolSearch (query "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_create_mcp"). Use tabs_context_mcp (createIfEmpty:true) e navigate para abrir a API pública do DJEN:

`https://comunicaapi.pje.jus.br/api/v1/comunicacao?pagina=1&itensPorPagina=100&numeroOab=229618&ufOab=RJ&dataDisponibilizacaoInicio=AAAA-MM-DD&dataDisponibilizacaoFim=AAAA-MM-DD`

Use como dataDisponibilizacaoInicio a data de ONTEM e como dataDisponibilizacaoFim a data de HOJE (fuso America/Sao_Paulo). Use javascript_tool com fetch() dentro da página (não use get_page_text, trunca JSON grande) para obter o JSON completo dos itens.

**2.** Para cada item em "items", classifique prioridade e prazo com estas regras:
- Se o campo "texto" estiver vazio/ausente: prioridade "SIGILO/ATENÇÃO", prazo não calculado, observação "sem teor disponível na API pública, possível sigilo".
- Senão, procure no texto um padrão tipo "em N dias" ou "prazo de N dias" (regex, N = número).
  - Se achou N dias E o tribunal (campo siglaTribunal) NÃO começa com "TRT" nem é "TST": calcule prazo em dias úteis — publicação = 1º dia útil após data_disponibilizacao; início = 1º dia útil após a publicação; prazo final = soma de N dias úteis a partir do início; prazo do escritório = 3 dias úteis antes do prazo final (excluindo fins de semana, sem considerar feriados forenses). Prioridade: "URGENTE" se N<=5, "ALTA" se N entre 6 e 15, "MÉDIA" se N>15.
  - Se achou N dias E o tribunal É trabalhista (TRT ou TST): prioridade "MÉDIA", NÃO calcule prazo (Justiça do Trabalho conta em dias corridos pela CLT, não dias úteis do CPC) — apenas sinalize "regra CLT (dias corridos) — requer conferência manual".
  - Se não achou dias mas o texto menciona "audiência" e uma data no formato dd/mm/aaaa: prioridade "MÉDIA", prazo fixo = essa data, observação "data fixa de audiência".
  - Se o texto sugere mero andamento (ex: "arquivamento", "sem saldo", "nomeação de perito", "lista de distribuição", "distribuído"): prioridade "BAIXA".
  - Caso contrário: prioridade "MÉDIA", observação "nenhum prazo identificado automaticamente — requer leitura manual do teor".

**3.** Gere um PDF (biblioteca reportlab) no formato "cards" já validado com Victor em sessões anteriores: título "Relatório Diário de Publicações e Prazos", nome/OAB de Victor e data, resumo numérico por prioridade (cores: SIGILO/ATENÇÃO roxo #7030A0, URGENTE vermelho #C00000, ALTA laranja #E36C09, MÉDIA azul-acinzentado #8EA9DB, BAIXA verde #A9D18E), agrupado por prioridade nessa ordem, um "card" por publicação contendo: processo (campo numeroprocessocommascara) e cliente/partes (nomes em "destinatarios"), tribunal/órgão, tipo de ato, teor (resumido), datas de disponibilização/publicação/início, prazo final e prazo sugerido do escritório (em vermelho), regra aplicada, sugestão de medida. Inclua aviso destacado (itálico vermelho) explicando que classificação e prazos são gerados automaticamente por heurísticas de texto, exigem validação humana obrigatória, não consideram feriados forenses locais, e que tribunais trabalhistas (TRT/TST) não têm prazo calculado automaticamente (regra CLT).

**4.** Gere também uma planilha Excel (openpyxl) com uma aba "Leia-me" explicando as mesmas limitações, e uma aba de dados com colunas: Prioridade, Processo, Cliente/Parte, Tribunal/Órgão, Tipo de ato, Teor, Disponibilização, Publicação, Início do prazo, Dias úteis do prazo, Prazo final, Prazo do escritório, Regra aplicada, Sugestão de medida — usando fórmulas do Excel (=WORKDAY(...)) para as colunas de datas calculadas automaticamente (não valores fixos), células de data como datetime.date reais (não texto). Cor de preenchimento da coluna Prioridade igual às cores do PDF.

**5.** Nomeie os arquivos como relatorio_prazos_AAAA-MM-DD.pdf e controle_prazos_AAAA-MM-DD.xlsx, usando a data de hoje.

**6.** Tente salvar os dois arquivos, via ponte com o computador do usuário (ferramentas mcp__remote-devices__*), na pasta: `C:\Users\advvi\OneDrive\Área de Trabalho\DIREITO\2. CASOS\6. PRAZOS` — pode ser necessário chamar device_request_folder_access para essa pasta primeiro, já que cada execução agendada é uma sessão nova sem acesso prévio. Se o usuário não aprovar rapidamente, ou o dispositivo/desktop não estiver conectado, apenas prossiga sem esta etapa (não trave a automação por causa disso).

**7.** SEMPRE entregue os dois arquivos também via SendUserFile no chat desta execução, independentemente do sucesso do passo 6, para garantir que Victor tenha acesso aos arquivos de qualquer forma. Envie com status "proactive" já que é uma execução agendada não observada.

**8.** Se a consulta ao DJEN retornar zero publicações no período, gere e envie os arquivos mesmo assim, deixando claro "nenhuma publicação encontrada no período consultado".

**9.** Se qualquer etapa falhar de forma irrecuperável (ex: navegador Claude in Chrome desconectado, extensão sem créditos), NÃO tente alternativas arriscadas — envie uma mensagem clara ao usuário explicando exatamente o que falhou e o que ele precisa verificar (ex: "abra o Chrome com a extensão Claude conectada e me avise para tentar de novo").

Não peça confirmação antes de agir — prossiga nesses passos de forma autônoma até o fim.

---

## Nota para o sistema próprio
A regra do passo 2 que trata TRT e TST como dias corridos está em conflito com o art. 775 da CLT (dias úteis desde a Lei 13.467/2017). Ver `CLAUDE.md`, regra 8, e `SPEC.md`, seção 9.
