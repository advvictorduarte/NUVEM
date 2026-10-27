"""Rotina diaria: coleta o DJEN, classifica e gera os dois relatorios.

Substitui a tarefa agendada que dependia do Chrome e da extensao. Roda em
qualquer computador com IP brasileiro.

    python -m coletor.principal                 # janela de ontem ate hoje
    python -m coletor.principal --dias 7        # ultimos 7 dias
    python -m coletor.principal --json arquivo  # usa um JSON ja baixado

Codigo de saida: 0 se tudo correu bem, 1 se a coleta falhou (os arquivos
sao gerados mesmo assim, dizendo o que falhou).
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "coletor"

from . import djen, regras, relatorio_pdf, relatorio_xlsx  # noqa: E402


def carrega_env(caminho=None):
    caminho = Path(caminho or Path(__file__).resolve().parents[1] / ".env")
    if not caminho.exists():
        return
    # utf-8-sig: o .env criado pelo PowerShell costuma vir com BOM
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"\''))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relatório diário de prazos do DJEN")
    ap.add_argument("--oab", default=None)
    ap.add_argument("--uf", default=None)
    ap.add_argument("--advogado", default=os.environ.get("ADVOGADO_NOME", ""))
    ap.add_argument("--dias", type=int, default=None,
                    help="janela em dias; sem isto usa de ontem até hoje")
    ap.add_argument("--saida", default="relatorios")
    ap.add_argument("--json", default=None,
                    help="usa um JSON já baixado em vez de chamar a API")
    args = ap.parse_args(argv)

    carrega_env()
    oab = args.oab or os.environ.get("OAB_NUMERO", "").strip()
    uf = (args.uf or os.environ.get("OAB_UF", "")).strip().upper()
    advogado = args.advogado or os.environ.get("ADVOGADO_NOME") or "—"
    if not args.json and (not oab or not uf):
        print("ERRO: defina OAB_NUMERO e OAB_UF no .env, ou use --oab/--uf.")
        return 2

    hoje = dt.date.today()
    if args.json:
        # utf-8-sig: o PowerShell grava com BOM quando usa -Encoding utf8
        bruto = json.loads(Path(args.json).read_text(encoding="utf-8-sig"))
        itens = bruto.get("items", bruto) if isinstance(bruto, dict) else bruto
        resultado = djen.ResultadoColeta()
        resultado.itens = itens
        resultado.completa = True
        resultado.inicio = resultado.fim = hoje
        resultado.total_informado = len(itens)
        print(f"Lidos {len(itens)} itens de {args.json}")
    else:
        inicio, fim = (hoje - dt.timedelta(days=args.dias), hoje) if args.dias \
            else djen.janela_padrao(hoje)
        print(f"Consultando o DJEN: OAB {oab}/{uf}, de {inicio} a {fim}")
        resultado = djen.coleta(oab, uf, inicio, fim)
        for p in resultado.paginas:
            print(f"  página {p['pagina']}: {p['itens']} itens, {p['segundos']}s")

    if resultado.erro:
        print(f"\nFALHA NA COLETA: {resultado.erro}")
        print("Os arquivos serão gerados assinalando a falha. "
              "NÃO se pode concluir que não houve publicações.")
    elif resultado.sem_publicacoes:
        print("\nNenhuma publicação no período. A consulta foi concluída com sucesso.")

    registros = regras.ordena_por_prioridade(regras.classifica_lote(resultado.itens))
    contagem = {}
    for r in registros:
        p = r["classificacao"]["prioridade"]
        contagem[p] = contagem.get(p, 0) + 1
    if registros:
        print("\nClassificação:")
        for p in regras.ORDEM_PRIORIDADE:
            if contagem.get(p):
                print(f"  {p:16s} {contagem[p]:>3}")
        sem_prazo = sum(1 for r in registros
                        if r["classificacao"]["dias"]
                        and r["classificacao"]["prazo_final"] is None)
        if sem_prazo:
            print(f"\n  {sem_prazo} publicação(ões) com prazo no texto mas SEM "
                  "cálculo automático (TRT/TST) — exigem conferência manual.")

    pasta = Path(args.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    resumo = resultado.resumo()
    pdf = pasta / f"relatorio_prazos_{hoje.isoformat()}.pdf"
    xlsx = pasta / f"controle_prazos_{hoje.isoformat()}.xlsx"
    relatorio_pdf.gera(registros, resumo, advogado, f"{oab}/{uf}", str(pdf), hoje)
    relatorio_xlsx.gera(registros, resumo, advogado, f"{oab}/{uf}", str(xlsx), hoje)
    print(f"\nGerados:\n  {pdf}\n  {xlsx}")
    return 0 if resultado.completa else 1


if __name__ == "__main__":
    raise SystemExit(main())
