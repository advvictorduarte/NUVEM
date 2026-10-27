"""Fase 1 - Teste B, parte 2: processos reais da carteira do escritorio.

Consulta no DataJud os numeros CNJ extraidos do controle de prazos e mede
a defasagem contra o que o escritorio ja sabe. Nao grava nome de cliente.

Uso: DATAJUD_API_KEY=... python3 scripts/fase1/datajud_carteira.py
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import carrega_env, grava, requisita_com_retry  # noqa: E402

# alias do indice, numero CNJ, rotulo do tipo de orgao (so para o relatorio)
CARTEIRA = [
    ("trt1", "0100233-80.2024.5.01.0302", "TRT1 - 2a VT de Petropolis"),
    ("trt1", "0100305-23.2023.5.01.0037", "TRT1 - 37a VT do Rio de Janeiro"),
    ("trt2", "1001400-79.2022.5.02.0422", "TRT2 - 2a VT de Santana de Parnaiba"),
    ("trf2", "5133743-17.2021.4.02.5101", "JF - 31a Vara Federal do RJ"),
    ("trf2", "5001454-83.2022.4.02.5102", "JEF - 6a Turma Recursal do RJ"),
    ("tjrj", "0814120-54.2026.8.19.0210", "JEC - 11o JEC da Leopoldina"),
    ("tjrj", "0884250-17.2026.8.19.0001", "JEC - 2o JEC da Capital"),
    ("tjrj", "3002811-24.2026.8.19.0208", "TJRJ - 3a Vara de Familia (SIGILOSO na planilha)"),
]


def main():
    carrega_env()
    chave = os.environ.get("DATAJUD_API_KEY", "").strip()
    if not chave:
        print("ERRO: DATAJUD_API_KEY nao definida.")
        return 2
    cab = {"Authorization": f"APIKey {chave}", "Content-Type": "application/json"}
    resultados = []
    for alias, numero, rotulo in CARTEIRA:
        digitos = "".join(filter(str.isdigit, numero))
        url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
        corpo = {"query": {"match": {"numeroProcesso": digitos}}, "size": 10}
        r = requisita_com_retry(url, "POST", corpo, cab, 180)
        time.sleep(4)  # espacar as chamadas: o DataJud devolve 429 sob rajada
        hits = ((r["json"] or {}).get("hits") or {}).get("hits") or []
        # Erro HTTP nunca vira "nao encontrado": vira "nao sei" (CLAUDE.md, regra 2)
        ok = r["status"] == 200 and r.get("confiavel", False)
        reg = {"alias": alias, "numero": numero, "rotulo": rotulo,
               "status": r["status"], "segundos": r["segundos"],
               "tentativas": r.get("tentativas"), "confiavel": r.get("confiavel"),
               "resultado": ("encontrado" if (ok and hits)
                             else "ausente" if ok else "INDETERMINADO"),
               "encontrado": bool(hits), "documentos": []}
        for h in hits:
            f = h["_source"]
            movs = [m.get("dataHora") for m in (f.get("movimentos") or [])
                    if m.get("dataHora")]
            reg["documentos"].append({
                "grau": f.get("grau"),
                "nivelSigilo": f.get("nivelSigilo"),
                "classe": (f.get("classe") or {}).get("nome"),
                "orgao": (f.get("orgaoJulgador") or {}).get("nome"),
                "qtd_movimentos": len(f.get("movimentos") or []),
                "ultimo_movimento": max(movs) if movs else None,
                "ultima_atualizacao": f.get("dataHoraUltimaAtualizacao"),
            })
        resultados.append(reg)
        marca = {"encontrado": "ENCONTRADO", "ausente": "AUSENTE",
                 "INDETERMINADO": f"INDETERMINADO (HTTP {r['status']})"}[reg["resultado"]]
        print(f"{marca:26s} {numero}  {rotulo}")
        for d in reg["documentos"]:
            print(f"      grau={d['grau']} sigilo={d['nivelSigilo']} "
                  f"movs={d['qtd_movimentos']} ultimo_mov={d['ultimo_movimento']} "
                  f"atualizado={d['ultima_atualizacao']}")
            print(f"      classe: {d['classe']} | orgao: {d['orgao']}")
    from collections import Counter
    c = Counter(r["resultado"] for r in resultados)
    print(f"\nEncontrados: {c['encontrado']} | Ausentes: {c['ausente']} | "
          f"Indeterminados: {c['INDETERMINADO']} (de {len(CARTEIRA)})")
    grava("datajud_carteira.json", resultados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
