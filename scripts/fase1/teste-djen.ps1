<#
Fase 1 - Teste A, item 2: a API do DJEN aceita chamada direta, sem navegador?
Rodar no computador do escritorio (Windows, rede brasileira), no PowerShell.

    cd <pasta do projeto>
    .\scripts\fase1\teste-djen.ps1 -Oab 229618 -Uf RJ

Resposta com "items" = chamada direta funciona, o coletor nao precisa do Chrome.
Erro 403 com "block access from your country" = bloqueio por pais (nao deve
acontecer de dentro do Brasil; se acontecer, anotar a mensagem exata).
#>
param(
  [Parameter(Mandatory = $true)][string]$Oab,
  [Parameter(Mandatory = $true)][string]$Uf,
  [int]$Dias = 7
)

$ErrorActionPreference = 'Stop'
$fim = (Get-Date).ToString('yyyy-MM-dd')
$ini = (Get-Date).AddDays(-$Dias).ToString('yyyy-MM-dd')
$url = "https://comunicaapi.pje.jus.br/api/v1/comunicacao" +
       "?pagina=1&itensPorPagina=100&numeroOab=$Oab&ufOab=$Uf" +
       "&dataDisponibilizacaoInicio=$ini&dataDisponibilizacaoFim=$fim"

Write-Host "Consultando o DJEN de $ini a $fim para a OAB $Oab/$Uf" -ForegroundColor Cyan
Write-Host $url -ForegroundColor DarkGray

$pasta = Join-Path $PSScriptRoot 'saida'
New-Item -ItemType Directory -Force -Path $pasta | Out-Null

try {
  $cronometro = [System.Diagnostics.Stopwatch]::StartNew()
  $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 120
  $cronometro.Stop()

  $itens = $resp.items
  Write-Host ""
  Write-Host "FUNCIONOU: chamada direta, sem navegador." -ForegroundColor Green
  Write-Host ("Tempo de resposta: {0:N2}s" -f $cronometro.Elapsed.TotalSeconds)
  Write-Host ("Itens nesta pagina: {0}" -f @($itens).Count)
  foreach ($p in $resp.PSObject.Properties) {
    if ($p.Name -ne 'items') { Write-Host ("Envelope: {0} = {1}" -f $p.Name, $p.Value) }
  }

  if (@($itens).Count -gt 0) {
    Write-Host ""
    Write-Host "Campos retornados em cada item:" -ForegroundColor Cyan
    $itens[0].PSObject.Properties.Name | Sort-Object | ForEach-Object { Write-Host "  - $_" }
    $semTexto = @($itens | Where-Object { [string]::IsNullOrWhiteSpace($_.texto) }).Count
    Write-Host ""
    Write-Host ("Itens sem o campo texto (possivel sigilo): {0} de {1}" -f $semTexto, @($itens).Count)
  }

  # Guarda o JSON cru para o relatorio da Fase 1. Contem dados de cliente:
  # fica fora do git (ver .gitignore) e nao deve ser colado no relatorio.
  $arquivo = Join-Path $pasta ("djen_powershell_{0}.json" -f (Get-Date -Format 'yyyy-MM-dd'))
  $resp | ConvertTo-Json -Depth 10 | Out-File -FilePath $arquivo -Encoding utf8
  Write-Host ""
  Write-Host "JSON cru salvo em: $arquivo" -ForegroundColor DarkGray
  Write-Host "Me mande o resumo (tempo, contagens, lista de campos), nao o JSON com nomes de clientes."
}
catch {
  Write-Host ""
  Write-Host "FALHOU. Mensagem exata, para o relatorio:" -ForegroundColor Red
  Write-Host $_.Exception.Message
  if ($_.Exception.Response) {
    $code = [int]$_.Exception.Response.StatusCode
    Write-Host ("Codigo HTTP: {0}" -f $code)
    try {
      $leitor = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
      $corpo = $leitor.ReadToEnd()
      Write-Host "Corpo da resposta (primeiros 800 caracteres):"
      Write-Host $corpo.Substring(0, [Math]::Min(800, $corpo.Length))
      if ($corpo -match 'block access from your country') {
        Write-Host ""
        Write-Host "=> Bloqueio por pais no CloudFront." -ForegroundColor Yellow
      }
    } catch {}
  }
  exit 1
}
