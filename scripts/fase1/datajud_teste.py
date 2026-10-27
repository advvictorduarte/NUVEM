"""Fase 1 - Teste B: API publica do DataJud (CNJ).

Valida acesso, consulta por numero CNJ, paginacao, ordenacao, sigilo,
comportamento em erro e tempo de resposta. Grava as respostas cruas em
scripts/fase1/saida/ e um resumo em datajud_resumo.json.

Uso:
    export DATAJUD_API_KEY=...        # ou preencher o .env
    python3 scripts/fase1/datajud_teste.py [--processos 00000000000000000000,...]

A chave vem de DATAJUD_API_KEY (wiki do CNJ) e nunca e gravada na saida.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import carrega_env, grava, requisita  # noqa: E402

BASE = "https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
# Aliases conferidos em https://datajud-wiki.cnj.jus.br/api-publica/endpoints/
ALIASES_TESTE = ["trt1", "tjrj", "trf2", "tst"]


def cabecalhos(chave):
    return {"Authorization": f"APIKey {chave}", "Content-Type": "application/json"}


def busca(alias, corpo, chave, timeout=120):
    return requisita(
        BASE.format(alias=alias), "POST", corpo, cabecalhos(chave), timeout
    )


def campos(fonte, prefixo=""):
    """Lista os caminhos de campo de um _source, sem os valores."""
    vistos = []
    if isinstance(fonte, dict):
        for k, v in fonte.items():
            vistos += campos(v, f"{prefixo}.{k}" if prefixo else k)
    elif isinstance(fonte, list):
        vistos.append(prefixo + "[]")
        if fonte and isinstance(fonte[0], (dict, list)):
            vistos += campos(fonte[0], prefixo + "[]")
    else:
        vistos.append(prefixo)
    return vistos


def capa(fonte):
    """Resumo da capa, somente metadado publico (o DataJud nao traz partes)."""
    movs = fonte.get("movimentos") or []
    datas = sorted(m.get("dataHora", "") for m in movs if m.get("dataHora"))
    return {
        "id": fonte.get("id"),
        "tribunal": fonte.get("tribunal"),
        "grau": fonte.get("grau"),
        "numeroProcesso": fonte.get("numeroProcesso"),
        "classe": (fonte.get("classe") or {}).get("nome"),
        "orgaoJulgador": (fonte.get("orgaoJulgador") or {}).get("nome"),
        "nivelSigilo": fonte.get("nivelSigilo"),
        "dataAjuizamento": fonte.get("dataAjuizamento"),
        "dataHoraUltimaAtualizacao": fonte.get("dataHoraUltimaAtualizacao"),
        "qtd_movimentos": len(movs),
        "primeiro_movimento": datas[0] if datas else None,
        "ultimo_movimento": datas[-1] if datas else None,
        "assuntos": [a.get("nome") for a in (fonte.get("assuntos") or [])][:5],
        "tipos_de_movimento": sorted({m.get("nome") for m in movs if m.get("nome")})[:15],
    }


def t1_acesso(chave, resumo):
    print("\n[T1] Acesso e estrutura por tribunal")
    resumo["t1_acesso"] = {}
    for alias in ALIASES_TESTE:
        r = busca(alias, {"size": 1, "query": {"match_all": {}}}, chave)
        item = {"status": r["status"], "segundos": r["segundos"], "erro": r.get("erro")}
        if r["json"] and r["json"].get("hits", {}).get("hits"):
            fonte = r["json"]["hits"]["hits"][0]["_source"]
            item["total_declarado"] = r["json"]["hits"]["total"]
            item["campos"] = campos(fonte)
            item["exemplo_capa"] = capa(fonte)
            grava(f"datajud_{alias}_amostra.json", r["json"])
        resumo["t1_acesso"][alias] = item
        print(f"  {alias:6s} HTTP {item['status']}  {item['segundos']:>7}s"
              f"  campos={len(item.get('campos', []))}")


def t2_por_numero(chave, processos, resumo):
    """Consulta por numero CNJ, que e o uso real do coletor."""
    print("\n[T2] Consulta por numeroProcesso")
    resumo["t2_por_numero"] = []
    for alias, numero in processos:
        corpo = {"query": {"match": {"numeroProcesso": numero}}, "size": 10}
        r = busca(alias, corpo, chave)
        achados = (r["json"] or {}).get("hits", {}).get("hits", [])
        reg = {
            "alias": alias,
            "numero_consultado": numero,
            "status": r["status"],
            "segundos": r["segundos"],
            "qtd_retornada": len(achados),
            "graus_retornados": sorted({h["_source"].get("grau") for h in achados}),
            "capas": [capa(h["_source"]) for h in achados[:3]],
        }
        resumo["t2_por_numero"].append(reg)
        print(f"  {alias:6s} {numero}  HTTP {r['status']}  "
              f"{reg['qtd_retornada']} doc(s)  graus={reg['graus_retornados']}")


def t3_paginacao(chave, resumo):
    print("\n[T3] Paginacao (size/from e search_after)")
    alias = "trt1"
    # Nao ordenar por _id: o Elasticsearch do DataJud recusa com HTTP 400
    # ("Fielddata access on the _id field is disallowed"). Desempate por _doc.
    ordem = [{"dataHoraUltimaAtualizacao": {"order": "desc"}}, {"_doc": "asc"}]
    p1 = busca(alias, {"size": 3, "from": 0, "query": {"match_all": {}}, "sort": ordem}, chave)
    p2 = busca(alias, {"size": 3, "from": 3, "query": {"match_all": {}}, "sort": ordem}, chave)
    ids1 = [h["_id"] for h in (p1["json"] or {}).get("hits", {}).get("hits", [])]
    ids2 = [h["_id"] for h in (p2["json"] or {}).get("hits", {}).get("hits", [])]
    sa = None
    hits1 = (p1["json"] or {}).get("hits", {}).get("hits", [])
    if hits1 and "sort" in hits1[-1]:
        sa = hits1[-1]["sort"]
    p3 = None
    if sa:
        p3 = busca(alias, {"size": 3, "query": {"match_all": {}}, "sort": ordem,
                           "search_after": sa}, chave)
    ids3 = [h["_id"] for h in ((p3 or {}).get("json") or {}).get("hits", {}).get("hits", [])]
    # Limite de janela profunda: from + size > 10000 e recusado (HTTP 400)
    fundo = busca(alias, {"size": 1, "from": 10000, "query": {"match_all": {}}}, chave)
    # Total exato so vem com track_total_hits; sem ele o hits.total para em 10000
    exato = busca(alias, {"size": 0, "query": {"match_all": {}},
                          "track_total_hits": True}, chave)
    # Ordenar por _id e proibido: registrar a recusa como evidencia
    por_id = busca(alias, {"size": 1, "query": {"match_all": {}},
                           "sort": [{"_id": "asc"}]}, chave)
    resumo["t3_paginacao"] = {
        "status_pagina1": p1["status"], "status_pagina2": p2["status"],
        "ids_pagina1": ids1, "ids_pagina2": ids2,
        "sobreposicao_from": sorted(set(ids1) & set(ids2)),
        "search_after_suportado": bool(ids3),
        "ids_search_after": ids3,
        "search_after_igual_pagina2": ids3 == ids2,
        "from_10000_status": fundo["status"],
        "from_10000_resposta": fundo["texto"][:300],
        "total_exato_com_track_total_hits":
            ((exato["json"] or {}).get("hits") or {}).get("total"),
        "sort_por_id_status": por_id["status"],
        "sort_por_id_resposta": por_id["texto"][:200],
    }
    print(f"  from=0/3 sem sobreposicao: {not resumo['t3_paginacao']['sobreposicao_from']}")
    print(f"  search_after suportado: {resumo['t3_paginacao']['search_after_suportado']}"
          f" (igual ao from: {resumo['t3_paginacao']['search_after_igual_pagina2']})")
    print(f"  from=10000 -> HTTP {fundo['status']}")


def t4_defasagem(chave, resumo):
    """Qual o movimento mais recente que cada tribunal expoe hoje."""
    print("\n[T4] Atualidade dos dados por tribunal")
    resumo["t4_defasagem"] = {}
    for alias in ALIASES_TESTE:
        corpo = {"size": 1, "query": {"match_all": {}},
                 "sort": [{"dataHoraUltimaAtualizacao": {"order": "desc"}}]}
        r = busca(alias, corpo, chave)
        hits = (r["json"] or {}).get("hits", {}).get("hits", [])
        mais_novo = hits[0]["_source"].get("dataHoraUltimaAtualizacao") if hits else None
        ult_mov = None
        if hits:
            movs = [m.get("dataHora") for m in (hits[0]["_source"].get("movimentos") or [])
                    if m.get("dataHora")]
            ult_mov = max(movs) if movs else None
        resumo["t4_defasagem"][alias] = {
            "status": r["status"],
            "ultima_atualizacao_mais_recente": mais_novo,
            "ultimo_movimento_desse_processo": ult_mov,
        }
        print(f"  {alias:6s} ultima atualizacao mais recente: {mais_novo}")


def t5_sigilo(chave, resumo):
    print("\n[T5] Niveis de sigilo expostos (agregacao)")
    resumo["t5_sigilo"] = {}
    for alias in ["trt1", "tjrj"]:
        corpo = {"size": 0, "query": {"match_all": {}},
                 "aggs": {"por_sigilo": {"terms": {"field": "nivelSigilo", "size": 10}}}}
        r = busca(alias, corpo, chave)
        baldes = (((r["json"] or {}).get("aggregations") or {}).get("por_sigilo") or {}).get("buckets")
        resumo["t5_sigilo"][alias] = {
            "status": r["status"],
            "agregacao_suportada": baldes is not None,
            "baldes": baldes,
            "resposta_em_erro": None if baldes is not None else r["texto"][:300],
        }
        print(f"  {alias:6s} agregacao: {baldes is not None}  {baldes}")


def t6_erros(chave, resumo):
    print("\n[T6] Comportamento em erro")
    casos = {}
    url = BASE.format(alias="trt1")
    corpo = {"size": 1, "query": {"match_all": {}}}
    casos["sem_chave"] = requisita(url, "POST", corpo, {"Content-Type": "application/json"}, 60)
    casos["chave_invalida"] = requisita(
        url, "POST", corpo, {"Authorization": "APIKey chave-invalida-de-teste",
                             "Content-Type": "application/json"}, 60)
    casos["alias_inexistente"] = requisita(
        BASE.format(alias="tjxx"), "POST", corpo, cabecalhos(chave), 60)
    casos["corpo_invalido"] = requisita(
        url, "POST", {"query": {"campo_que_nao_existe": {"x": 1}}}, cabecalhos(chave), 60)
    casos["metodo_get"] = requisita(url, "GET", None, cabecalhos(chave), 60)
    resumo["t6_erros"] = {
        k: {"status": v["status"], "segundos": v["segundos"],
            "erro": v.get("erro"), "resposta": v["texto"][:400]}
        for k, v in casos.items()
    }
    for k, v in resumo["t6_erros"].items():
        print(f"  {k:18s} HTTP {v['status']}")


def t7_limites(chave, resumo, repeticoes=12):
    """Rajada curta para observar bloqueio por volume (HTTP 429)."""
    print(f"\n[T7] Limite de requisicoes ({repeticoes} chamadas seguidas)")
    tempos, status = [], []
    for i in range(repeticoes):
        r = busca("trt1", {"size": 1, "query": {"match_all": {}}}, chave, timeout=120)
        tempos.append(r["segundos"])
        status.append(r["status"])
    ok = [t for t, s in zip(tempos, status) if s == 200]
    resumo["t7_limites"] = {
        "repeticoes": repeticoes,
        "status_observados": sorted(set(map(str, status))),
        "houve_429": 429 in status,
        "tempo_min": min(ok) if ok else None,
        "tempo_max": max(ok) if ok else None,
        "tempo_medio": round(sum(ok) / len(ok), 3) if ok else None,
        "tempos": tempos,
    }
    print(f"  status: {resumo['t7_limites']['status_observados']}  "
          f"429: {resumo['t7_limites']['houve_429']}  "
          f"tempo min/med/max: {resumo['t7_limites']['tempo_min']}/"
          f"{resumo['t7_limites']['tempo_medio']}/{resumo['t7_limites']['tempo_max']}s")


def amostra_numeros(chave):
    """Pega numeros CNJ reais de cada tribunal para alimentar o T2.

    Usado so quando o advogado nao passa --processos. Sao processos
    publicos quaisquer, nao da carteira do escritorio.
    """
    saida = []
    for alias in ["trt1", "tjrj", "trf2"]:
        r = busca(alias, {"size": 1, "query": {"match_all": {}}}, chave)
        hits = (r["json"] or {}).get("hits", {}).get("hits", [])
        if hits:
            saida.append((alias, hits[0]["_source"]["numeroProcesso"]))
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processos", default="",
                    help="lista alias:numero separada por virgula, ex: tjrj:0034...")
    ap.add_argument("--pular-limites", action="store_true")
    args = ap.parse_args()

    carrega_env()
    chave = os.environ.get("DATAJUD_API_KEY", "").strip()
    if not chave:
        print("ERRO: DATAJUD_API_KEY nao definida. Ver .env.example e a wiki do CNJ:")
        print("  https://datajud-wiki.cnj.jus.br/api-publica/acesso/")
        return 2

    resumo = {"fonte": "DataJud - API publica do CNJ", "base": BASE,
              "aliases_testados": ALIASES_TESTE}
    t1_acesso(chave, resumo)

    if args.processos:
        processos = []
        for par in args.processos.split(","):
            alias, _, numero = par.strip().partition(":")
            if alias and numero:
                processos.append((alias.lower(), "".join(filter(str.isdigit, numero))))
        resumo["origem_dos_processos"] = "lista informada pelo advogado"
    else:
        processos = amostra_numeros(chave)
        resumo["origem_dos_processos"] = (
            "amostra publica colhida do proprio DataJud (o advogado nao informou CNJs)")
    t2_por_numero(chave, processos, resumo)
    t3_paginacao(chave, resumo)
    t4_defasagem(chave, resumo)
    t5_sigilo(chave, resumo)
    t6_erros(chave, resumo)
    if not args.pular_limites:
        t7_limites(chave, resumo)

    destino = grava("datajud_resumo.json", resumo)
    print(f"\nResumo gravado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
