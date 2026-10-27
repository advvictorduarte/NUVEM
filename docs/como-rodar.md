# Como rodar o relatório diário

Substitui a tarefa agendada que dependia do Chrome e da extensão. **Precisa rodar de uma rede brasileira** — a API do DJEN recusa requisição de fora do Brasil.

## Passo 0 — pôr o projeto no seu computador

Os arquivos do projeto não nascem no seu computador: eles vêm no arquivo `monitoramento-prazos.zip`.

1. Baixar o `.zip` e **descompactar** numa pasta sua, por exemplo `C:\Users\advvi\monitoramento-prazos`.
2. Abrir o PowerShell **nessa pasta**: abrir a pasta no Explorador, clicar na barra de endereço, escrever `powershell` e apertar Enter.
3. Conferir que está no lugar certo — o comando abaixo tem de listar `coletor`, `docs` e `testes`:

```powershell
dir
```

Se der erro de "não reconhecido", é porque o PowerShell está em outra pasta. Volte ao passo 2.

## Passo 1 — preparar, uma vez só

1. Instalar o Python 3 (se ainda não tiver): <https://www.python.org/downloads/windows/> — marcar "Add Python to PATH" na instalação.
2. No PowerShell, dentro da pasta do projeto:

```powershell
pip install reportlab openpyxl
copy .env.example .env
```

3. Abrir o `.env` no bloco de notas e preencher:

```
OAB_NUMERO=229618
OAB_UF=RJ
ADVOGADO_NOME=Victor Duarte de Sousa
```

O `.env` **não** vai para o git (já está no `.gitignore`).

## Passo 2 — todo dia

```powershell
python -m coletor.principal
```

Consulta de ontem até hoje, classifica, e grava os dois arquivos em `relatorios\`:

- `relatorio_prazos_AAAA-MM-DD.pdf`
- `controle_prazos_AAAA-MM-DD.xlsx`

## Variações

| Comando | O que faz |
| --- | --- |
| `python -m coletor.principal --dias 30` | últimos 30 dias, em vez de ontem e hoje |
| `python -m coletor.principal --saida "C:\Users\advvi\OneDrive\Área de Trabalho\DIREITO\2. CASOS\6. PRAZOS"` | grava direto na pasta de prazos |
| `python -m coletor.principal --json arquivo.json` | usa um JSON já baixado, sem chamar a API |

## Como saber se deu certo

A última linha diz onde os arquivos foram gravados. Além disso:

- **Código de saída 0** — a coleta foi completa.
- **Código de saída 1** — a coleta falhou. Os arquivos **são gerados assim mesmo**, com um aviso em vermelho no topo dizendo o que falhou. Nesse caso **não se pode concluir que não houve publicações** — só que não foi possível saber.

Para agendar, use o Agendador de Tarefas do Windows apontando para o mesmo comando. Enquanto isso não for feito, a tarefa agendada atual continua rodando normalmente — uma coisa não atrapalha a outra.

## Rodar os testes

```powershell
python -m unittest discover -s testes
```

São 22 testes sobre a contagem de prazo em dias úteis, as seis regras de classificação e a deduplicação, como pede o `CLAUDE.md`. Os casos de contagem usam datas reais conferidas no controle de prazos do escritório.
