"""Coleta de publicacoes no DJEN, por chamada direta (sem navegador).

Validado na Fase 1: a API responde a GET simples em 0,8 s, sem chave e sem
cadastro, desde que a requisicao saia de um IP brasileiro. De fora do Brasil
o CloudFront devolve 403 por pais.

Regra que nao pode ser quebrada (CLAUDE.md, regra 2): falha de coleta nunca
vira "nenhuma publicacao". Por isso a coleta devolve um resultado com
`completa`, e quem chama precisa olhar esse campo antes de afirmar qualquer
coisa sobre ausencia de publicacoes.
"""
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
ITENS_POR_PAGINA = 100
MAX_PAGINAS = 100


class ResultadoColeta:
    """O que a coleta devolve. Distingue 'nada' de 'nao sei'."""

    def __init__(self):
        self.itens = []
        self.completa = False
        self.erro = None
        self.total_informado = None
        self.paginas = []
        self.inicio = None
        self.fim = None

    @property
    def sem_publicacoes(self):
        """So e verdade se a coleta funcionou e nao trouxe nada."""
        return self.completa and not self.itens

    def resumo(self):
        return {
            "periodo": {"inicio": str(self.inicio), "fim": str(self.fim)},
            "completa": self.completa,
            "erro": self.erro,
            "itens": len(self.itens),
            "total_informado_pela_api": self.total_informado,
            "paginas": self.paginas,
        }


def _chama(parametros, timeout=120, tentativas=3):
    url = f"{BASE}?{urllib.parse.urlencode(parametros)}"
    espera = 3
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        requisicao = urllib.request.Request(
            url, headers={"Accept": "application/json"})
        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
                bruto = resposta.read()
            segundos = round(time.monotonic() - inicio, 2)
            return json.loads(bruto.decode("utf-8")), segundos, None
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", errors="replace")
            if e.code == 403 and "block access from your country" in corpo:
                return None, 0, ("A API do DJEN recusou este computador por país "
                                 "(bloqueio do CloudFront). A coleta precisa rodar "
                                 "de uma rede brasileira.")
            ultimo_erro = f"HTTP {e.code}"
        except json.JSONDecodeError:
            ultimo_erro = "a resposta não é JSON válido"
        except Exception as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
        if tentativa < tentativas:
            time.sleep(espera)
            espera *= 2
    return None, 0, ultimo_erro


def coleta(oab, uf, data_inicio, data_fim, timeout=120):
    """Percorre todas as paginas do periodo. Nunca engole erro."""
    resultado = ResultadoColeta()
    resultado.inicio, resultado.fim = data_inicio, data_fim
    pagina = 1
    while pagina <= MAX_PAGINAS:
        parametros = {
            "pagina": pagina,
            "itensPorPagina": ITENS_POR_PAGINA,
            "numeroOab": oab,
            "ufOab": uf,
            "dataDisponibilizacaoInicio": data_inicio.isoformat(),
            "dataDisponibilizacaoFim": data_fim.isoformat(),
        }
        corpo, segundos, erro = _chama(parametros, timeout)
        if erro:
            resultado.erro = f"página {pagina}: {erro}"
            resultado.completa = False
            return resultado
        lote = corpo.get("items") or []
        if pagina == 1:
            resultado.total_informado = corpo.get("count")
        resultado.paginas.append({"pagina": pagina, "itens": len(lote),
                                  "segundos": segundos})
        resultado.itens.extend(lote)
        if len(lote) < ITENS_POR_PAGINA:
            break
        pagina += 1
    else:
        resultado.erro = (f"a coleta passou de {MAX_PAGINAS} páginas e foi "
                          "interrompida por segurança")
        return resultado

    resultado.completa = True
    # Conferencia contra o total que a propria API informa
    total = resultado.total_informado
    if total is not None and total != len(resultado.itens):
        resultado.completa = False
        resultado.erro = (f"a API informou {total} publicações no período, "
                          f"mas foram coletadas {len(resultado.itens)}")
    return resultado


def janela_padrao(hoje=None):
    """Janela da automacao vigente: de ontem ate hoje."""
    hoje = hoje or dt.date.today()
    return hoje - dt.timedelta(days=1), hoje
