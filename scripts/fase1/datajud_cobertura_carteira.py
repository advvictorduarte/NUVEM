"""Fase 1 - Teste B, parte 3: cobertura da carteira inteira no DataJud.

Le os numeros CNJ do controle de prazos do escritorio, agrupa por indice
de tribunal e faz UMA consulta 'terms' por indice (ate 1024 numeros por
consulta), em vez de uma consulta por processo. Responde: quantos dos
processos do escritorio o DataJud conhece, por ramo da Justica.

Nao le nem grava nome de cliente: so numero de processo e metadado.

Uso: DATAJUD_API_KEY=... python3 scripts/fase1/datajud_cobertura_carteira.py <planilha.xlsx>
"""
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import carrega_env, grava, requisita_com_retry  # noqa: E402

RX = re.compile(r"(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})")
RAMO = {"4": "Justiça Federal", "5": "Justiça do Trabalho", "8": "Justiça Estadual"}


def indice(j, tr):
    """Mapeia segmento (J) e tribunal (TR) do numero CNJ para o alias."""
    if j == "5":
        return f"trt{int(tr)}"
    if j == "8":
        return {"19": "tjrj"}.get(tr)
    if j == "4":
        return f"trf{int(tr)}"
    return None


def le_numeros(caminho):
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    numeros = {}
    for aba in wb.sheetnames:
        ws = wb[aba]
        for linha in ws.iter_rows(values_only=True):
            for celula in linha:
                if not celula:
                    continue
                m = RX.search(str(celula))
                if m:
                    numeros[m.group(0)] = (m.group(4), m.group(5))
    return numeros


def main():
    if len(sys.argv) < 2:
        print("uso: datajud_cobertura_carteira.py <planilha.xlsx>")
        return 2
    carrega_env()
    chave = os.environ.get("DATAJUD_API_KEY", "").strip()
    if not chave:
        print("ERRO: DATAJUD_API_KEY nao definida.")
        return 2
    cab = {"Authorization": f"APIKey {chave}", "Content-Type": "application/json"}

    numeros = le_numeros(sys.argv[1])
    por_indice = defaultdict(list)
    sem_indice = []
    for num, (j, tr) in numeros.items():
        al = indice(j, tr)
        (por_indice[al] if al else sem_indice).append(num)
    print(f"Processos distintos na planilha: {len(numeros)}")
    if sem_indice:
        print(f"Sem indice mapeado: {len(sem_indice)}")

    resumo = {"total_planilha": len(numeros), "por_indice": {}}
    for al in sorted(por_indice):
        lista = por_indice[al]
        digitos = ["".join(filter(str.isdigit, n)) for n in lista]
        corpo = {"size": 1000, "track_total_hits": True,
                 "query": {"terms": {"numeroProcesso": digitos[:1024]}},
                 "_source": ["numeroProcesso", "grau", "nivelSigilo",
                             "dataHoraUltimaAtualizacao"]}
        url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{al}/_search"
        r = requisita_com_retry(url, "POST", corpo, cab, 180)
        time.sleep(4)
        if r["status"] != 200 or not r.get("confiavel"):
            print(f"  {al:7s} INDETERMINADO (HTTP {r['status']}, "
                  f"confiavel={r.get('confiavel')}) — {len(lista)} processos")
            resumo["por_indice"][al] = {"consultados": len(lista),
                                        "resultado": "INDETERMINADO",
                                        "status": r["status"]}
            continue
        hits = ((r["json"] or {}).get("hits") or {}).get("hits") or []
        achados = {h["_source"]["numeroProcesso"] for h in hits}
        graus = defaultdict(int)
        for h in hits:
            graus[h["_source"].get("grau")] += 1
        faltando = [n for n, d in zip(lista, digitos) if d not in achados]
        pct = 100 * len(achados) / len(lista) if lista else 0
        print(f"  {al:7s} {len(achados):>4} de {len(lista):<4} processos "
              f"({pct:5.1f}%)  {len(hits)} documentos  graus={dict(graus)}")
        resumo["por_indice"][al] = {
            "consultados": len(lista), "encontrados": len(achados),
            "percentual": round(pct, 1), "documentos": len(hits),
            "graus": dict(graus), "ausentes": faltando,
            "resultado": "ok",
        }

    oks = [v for v in resumo["por_indice"].values() if v.get("resultado") == "ok"]
    tot_c = sum(v["consultados"] for v in oks)
    tot_e = sum(v["encontrados"] for v in oks)
    if tot_c:
        print(f"\nCobertura total apurada: {tot_e} de {tot_c} "
              f"({100*tot_e/tot_c:.1f}%)")
        resumo["cobertura_total"] = {"consultados": tot_c, "encontrados": tot_e,
                                     "percentual": round(100*tot_e/tot_c, 1)}
    grava("datajud_cobertura_carteira.json", resumo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
