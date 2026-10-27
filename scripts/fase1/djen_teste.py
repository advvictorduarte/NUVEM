"""Fase 1 - Teste A: API de comunicacoes do DJEN (CNJ).

Testa a chamada DIRETA, fora do navegador, e registra o que funciona e o
que e recusado. Precisa rodar de um IP brasileiro: o CloudFront do
comunicaapi.pje.jus.br bloqueia por pais (ver docs/fase1-relatorio.md).

Uso (no computador do advogado, com .env preenchido):
    python3 scripts/fase1/djen_teste.py --dias 30

Nao grava texto de publicacao nem nome de parte no resumo (CLAUDE.md,
regra 7): o resumo traz contagens, nomes de campo e exemplos mascarados.
As respostas cruas ficam em scripts/fase1/saida/ (fora do git) para
conferencia do advogado.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import carrega_env, grava, mascara, requisita  # noqa: E402

BASE = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
CAMPOS_SENSIVEIS = {"texto", "destinatarios", "destinatarioadvogados", "nomeparte"}


def chama(params, timeout=90):
    return requisita(f"{BASE}?{urlencode(params)}", "GET", None,
                     {"Accept": "application/json"}, timeout)


def diagnostico(r):
    """Reconhece o bloqueio por pais e outros erros tipicos."""
    if r["status"] is None:
        return f"falha de rede: {r.get('erro')}"
    t = r["texto"] or ""
    if r["status"] == 403 and "block access from your country" in t:
        return "BLOQUEIO POR PAIS (CloudFront) - rodar de IP brasileiro"
    if r["status"] == 403 and "CloudFront" in t:
        return "403 do CloudFront - ver corpo da resposta"
    if r["status"] == 200 and r["json"] is None:
        return "HTTP 200 mas corpo nao e JSON (pagina de verificacao?)"
    if r["status"] == 200:
        return "ok"
    return f"HTTP {r['status']}"


def estrutura(itens):
    """Nomes de campo presentes, com tipo e preenchimento."""
    visao = {}
    for it in itens:
        for k, v in it.items():
            reg = visao.setdefault(k, {"tipo": type(v).__name__, "vazios": 0,
                                       "preenchidos": 0, "exemplo": None})
            if v in (None, "", [], {}):
                reg["vazios"] += 1
            else:
                reg["preenchidos"] += 1
                if reg["exemplo"] is None and k not in CAMPOS_SENSIVEIS:
                    reg["exemplo"] = mascara(str(v))[:120]
    return visao


def t1_parametros(oab, uf, hoje, resumo):
    """Descobre quais parametros a API aceita e quais recusa."""
    print("\n[T1] Parametros aceitos e recusados")
    ini = (hoje - timedelta(days=7)).isoformat()
    fim = hoje.isoformat()
    base = {"pagina": 1, "itensPorPagina": 5, "numeroOab": oab, "ufOab": uf,
            "dataDisponibilizacaoInicio": ini, "dataDisponibilizacaoFim": fim}
    casos = {
        "automacao_atual": dict(base),
        "sem_datas": {"pagina": 1, "itensPorPagina": 5, "numeroOab": oab, "ufOab": uf},
        "sem_oab_so_datas": {"pagina": 1, "itensPorPagina": 5,
                             "dataDisponibilizacaoInicio": fim,
                             "dataDisponibilizacaoFim": fim},
        "itensPorPagina_1000": dict(base, itensPorPagina=1000),
        "itensPorPagina_200": dict(base, itensPorPagina=200),
        "com_siglaTribunal": dict(base, siglaTribunal="TRT1"),
        "com_meio_D": dict(base, meio="D"),
        "oab_com_pontos": dict(base, numeroOab="229.618"),
        "uf_minuscula": dict(base, ufOab=uf.lower()),
        "data_invertida": dict(base, dataDisponibilizacaoInicio=fim,
                               dataDisponibilizacaoFim=ini),
        "data_formato_br": dict(base, dataDisponibilizacaoInicio="01/10/2026",
                                dataDisponibilizacaoFim="26/10/2026"),
        "pagina_zero": dict(base, pagina=0),
    }
    resumo["t1_parametros"] = {}
    for nome, params in casos.items():
        r = chama(params)
        corpo = r["json"] if isinstance(r["json"], dict) else {}
        itens = corpo.get("items") or corpo.get("content") or []
        reg = {"status": r["status"], "segundos": r["segundos"],
               "diagnostico": diagnostico(r),
               "qtd_itens": len(itens) if isinstance(itens, list) else None,
               "chaves_do_envelope": sorted(corpo.keys()) if corpo else None,
               "resposta_em_erro": None if r["status"] == 200 else mascara(r["texto"])[:300]}
        resumo["t1_parametros"][nome] = reg
        print(f"  {nome:22s} HTTP {str(reg['status']):>4}  itens={reg['qtd_itens']}"
              f"  {reg['diagnostico']}")


def t2_coleta(oab, uf, dias, hoje, resumo):
    """Percorre todas as paginas do periodo e mede o comportamento."""
    print(f"\n[T2] Coleta dos ultimos {dias} dias, todas as paginas")
    ini = (hoje - timedelta(days=dias)).isoformat()
    fim = hoje.isoformat()
    itens, paginas, pagina = [], [], 1
    envelope_1a_pagina = None
    while True:
        params = {"pagina": pagina, "itensPorPagina": 100, "numeroOab": oab,
                  "ufOab": uf, "dataDisponibilizacaoInicio": ini,
                  "dataDisponibilizacaoFim": fim}
        r = chama(params, timeout=120)
        corpo = r["json"] if isinstance(r["json"], dict) else {}
        lote = corpo.get("items") or []
        paginas.append({"pagina": pagina, "status": r["status"],
                        "segundos": r["segundos"], "qtd": len(lote),
                        "diagnostico": diagnostico(r)})
        print(f"  pagina {pagina:>3}: HTTP {r['status']}  {len(lote):>4} itens"
              f"  {r['segundos']}s")
        if pagina == 1:
            envelope_1a_pagina = {k: v for k, v in corpo.items() if k != "items"}
            grava("djen_pagina1_cru.json", corpo)
        if r["status"] != 200 or not lote:
            break
        itens += lote
        if len(lote) < 100:
            break
        pagina += 1
        if pagina > 60:
            print("  parado em 60 paginas por seguranca")
            break

    sem_texto = [i for i in itens if not (i.get("texto") or "").strip()]
    ids = [i.get("id") for i in itens]
    resumo["t2_coleta"] = {
        "periodo": {"inicio": ini, "fim": fim},
        "paginas": paginas,
        "total_itens": len(itens),
        "envelope_1a_pagina": envelope_1a_pagina,
        "ids_repetidos": len(ids) - len(set(ids)),
        "itens_sem_texto": len(sem_texto),
        "campos": estrutura(itens) if itens else {},
        "tribunais": sorted({str(i.get("siglaTribunal")) for i in itens}),
        "datas_disponibilizacao": sorted({str(i.get("data_disponibilizacao"))
                                          for i in itens}),
    }
    # Cruzamento sigilo x texto vazio: a automacao atual supoe que texto
    # vazio = sigilo. Aqui so registramos os campos que podem confirmar.
    if sem_texto:
        resumo["t2_coleta"]["amostra_sem_texto"] = [
            {k: mascara(str(v))[:80] for k, v in i.items()
             if k not in CAMPOS_SENSIVEIS}
            for i in sem_texto[:5]
        ]
    if itens:
        grava("djen_itens_crus.json", itens)
    print(f"  total: {len(itens)} itens, {len(sem_texto)} sem texto, "
          f"{resumo['t2_coleta']['ids_repetidos']} id(s) repetido(s)")


def t3_rajada(oab, uf, hoje, resumo, repeticoes=15):
    print(f"\n[T3] Limite de requisicoes ({repeticoes} chamadas seguidas)")
    fim = hoje.isoformat()
    status, tempos = [], []
    for _ in range(repeticoes):
        r = chama({"pagina": 1, "itensPorPagina": 1, "numeroOab": oab, "ufOab": uf,
                   "dataDisponibilizacaoInicio": fim, "dataDisponibilizacaoFim": fim}, 60)
        status.append(r["status"])
        tempos.append(r["segundos"])
    ok = [t for t, s in zip(tempos, status) if s == 200]
    resumo["t3_rajada"] = {
        "repeticoes": repeticoes,
        "status_observados": sorted(set(map(str, status))),
        "houve_429": 429 in status,
        "tempo_min": min(ok) if ok else None,
        "tempo_max": max(ok) if ok else None,
        "tempo_medio": round(sum(ok) / len(ok), 3) if ok else None,
    }
    print(f"  status: {resumo['t3_rajada']['status_observados']}  "
          f"429: {resumo['t3_rajada']['houve_429']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--oab", default=None)
    ap.add_argument("--uf", default=None)
    ap.add_argument("--pular-rajada", action="store_true")
    args = ap.parse_args()

    carrega_env()
    oab = args.oab or os.environ.get("OAB_NUMERO", "").strip()
    uf = (args.uf or os.environ.get("OAB_UF", "")).strip().upper()
    if not oab or not uf:
        print("ERRO: defina OAB_NUMERO e OAB_UF no .env (ver .env.example) "
              "ou passe --oab/--uf.")
        return 2

    hoje = date.today()
    resumo = {"fonte": "DJEN - API de comunicacoes do CNJ", "base": BASE,
              "executado_em": hoje.isoformat(), "oab_consultada": f"{oab}/{uf}"}

    # Sonda primeiro: se o IP esta bloqueado, nada mais faz sentido.
    sonda = chama({"pagina": 1, "itensPorPagina": 1, "numeroOab": oab, "ufOab": uf,
                   "dataDisponibilizacaoInicio": hoje.isoformat(),
                   "dataDisponibilizacaoFim": hoje.isoformat()}, 60)
    resumo["sonda"] = {"status": sonda["status"], "segundos": sonda["segundos"],
                       "diagnostico": diagnostico(sonda),
                       "resposta": mascara(sonda["texto"])[:500]}
    print(f"[sonda] HTTP {sonda['status']} - {resumo['sonda']['diagnostico']}")
    if resumo["sonda"]["diagnostico"].startswith("BLOQUEIO POR PAIS"):
        print("\nA API recusou este IP por pais. Rode este script de uma rede")
        print("brasileira (o computador do escritorio) e repita.")
        grava("djen_resumo.json", resumo)
        return 1

    t1_parametros(oab, uf, hoje, resumo)
    t2_coleta(oab, uf, args.dias, hoje, resumo)
    if not args.pular_rajada:
        t3_rajada(oab, uf, hoje, resumo)
    destino = grava("djen_resumo.json", resumo)
    print(f"\nResumo gravado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
