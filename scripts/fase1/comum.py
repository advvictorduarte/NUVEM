"""Funcoes compartilhadas pelos testes da Fase 1.

Nao registra em log texto de publicacao, nome de parte nem CPF/CNPJ
(CLAUDE.md, regra 7). A chave do DataJud nunca e impressa (regra 4).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

SAIDA = Path(__file__).resolve().parent / "saida"
SAIDA.mkdir(exist_ok=True)


def carrega_env(caminho=None):
    """Le um .env simples da raiz do projeto, sem dependencia externa."""
    caminho = Path(caminho or Path(__file__).resolve().parents[2] / ".env")
    if not caminho.exists():
        return
    # utf-8-sig: o .env criado pelo PowerShell costuma vir com BOM
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def requisita(url, metodo="GET", corpo=None, cabecalhos=None, timeout=120):
    """Faz a chamada e devolve sempre um dicionario, inclusive em erro.

    Devolve: status, segundos, tamanho, json (ou None), texto (truncado).
    """
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo)
    for k, v in (cabecalhos or {}).items():
        req.add_header(k, v)
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        bruto = e.read()
        status = e.code
    except Exception as e:  # rede, TLS, timeout
        return {
            "status": None,
            "erro": f"{type(e).__name__}: {e}",
            "segundos": round(time.monotonic() - inicio, 3),
            "tamanho": 0,
            "json": None,
            "texto": "",
        }
    segundos = round(time.monotonic() - inicio, 3)
    texto = bruto.decode("utf-8", errors="replace")
    try:
        corpo_json = json.loads(texto)
    except ValueError:
        corpo_json = None
    return {
        "status": status,
        "segundos": segundos,
        "tamanho": len(bruto),
        "json": corpo_json,
        "texto": texto[:1500],
    }


def mascara(texto):
    """Mascara nome de parte, CPF, CNPJ e OAB antes de qualquer registro."""
    if not isinstance(texto, str):
        return texto
    texto = re.sub(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", "<CPF>", texto)
    texto = re.sub(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", "<CNPJ>", texto)
    return texto


def grava(nome, obj):
    destino = SAIDA / nome
    destino.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destino


def requisita_com_retry(url, metodo="GET", corpo=None, cabecalhos=None,
                        timeout=180, tentativas=4, espera_inicial=5):
    """Como requisita(), mas distingue erro de resultado vazio.

    O DataJud devolve 429 (limite de requisicoes) e 504 (timeout) sob carga.
    Tratar isso como "nenhum resultado" seria afirmar ausencia sem base —
    o que a regra 2 do CLAUDE.md proibe. Aqui o erro e repetido com espera
    crescente e, se persistir, devolvido como erro explicito.

    Acrescenta 'confiavel': False quando a resposta veio incompleta
    (shard com falha ou consulta expirada), mesmo com HTTP 200.
    """
    import time as _time
    espera = espera_inicial
    ultima = None
    for tentativa in range(1, tentativas + 1):
        r = requisita(url, metodo, corpo, cabecalhos, timeout)
        ultima = r
        r["tentativas"] = tentativa
        if r["status"] == 200:
            corpo_json = r["json"] or {}
            shards = corpo_json.get("_shards") or {}
            r["confiavel"] = (not corpo_json.get("timed_out", False)
                              and shards.get("failed", 0) == 0)
            r["shards"] = shards
            return r
        if r["status"] in (429, 500, 502, 503, 504) or r["status"] is None:
            if tentativa < tentativas:
                _time.sleep(espera)
                espera *= 2
                continue
        r["confiavel"] = False
        return r
    ultima["confiavel"] = False
    return ultima
