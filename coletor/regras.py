"""Regras vigentes de classificacao e contagem de prazo.

Implementa `docs/regras-classificacao.md`, decidido pelo advogado em
27/10/2026: valem as regras da automacao agendada atual, como estao.

Nao considera feriado forense nem o recesso de 20/12 a 20/01, por decisao.
Nao calcula prazo de TRT nem TST, por decisao.
"""
import datetime as dt
import html
import re
import unicodedata

# --- Prioridades, na ordem em que aparecem no relatorio ---
SIGILO = "SIGILO/ATENÇÃO"
URGENTE = "URGENTE"
ALTA = "ALTA"
MEDIA = "MÉDIA"
BAIXA = "BAIXA"
ORDEM_PRIORIDADE = [SIGILO, URGENTE, ALTA, MEDIA, BAIXA]

CORES = {
    SIGILO: "7030A0",
    URGENTE: "C00000",
    ALTA: "E36C09",
    MEDIA: "8EA9DB",
    BAIXA: "A9D18E",
}

# Quantos dias uteis antes do prazo final fica o prazo interno do escritorio
FOLGA_ESCRITORIO = 3

# Como contar os N dias uteis a partir do inicio.
#   True  -> o dia de inicio conta como dia 1 (final = inicio + N-1 dias uteis)
#   False -> a contagem comeca no dia util seguinte ao inicio (final = inicio + N)
# O texto da automacao ("soma de N dias uteis a partir do inicio") admite as
# duas leituras, e o historico do escritorio usa ora uma, ora outra. Adotada a
# primeira, que segue o art. 224 do CPC: exclui-se o dia do comeco (a
# publicacao) e inclui-se o do vencimento. Trocar aqui muda todo o sistema.
INICIO_CONTA_COMO_DIA_1 = True

RX_DIAS = re.compile(r"\b(?:em|prazo de)\s+(\d{1,3})\s+dias\b", re.IGNORECASE)
RX_DATA_BR = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
RX_AUDIENCIA = re.compile(r"audi[êe]ncia", re.IGNORECASE)

TERMOS_ANDAMENTO = ("arquivamento", "sem saldo", "nomeacao de perito",
                    "lista de distribuicao", "distribuido")


RX_TAG = re.compile(r"<[^>]+>")
RX_BR = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
RX_ESPACO = re.compile(r"\s+")


def limpa_texto(bruto):
    """Tira o HTML que o DJEN manda no campo `texto`.

    O teor vem com <br> e entidades HTML. Isso quebra o gerador de PDF e
    atrapalha a busca do prazo, entao a limpeza vale para os dois usos.
    """
    if not bruto:
        return ""
    texto = RX_BR.sub(" ", str(bruto))
    texto = RX_TAG.sub(" ", texto)
    texto = html.unescape(texto)
    # Depois do unescape pode sobrar < ou & solto, que o reportlab recusa
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return RX_ESPACO.sub(" ", texto).strip()


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


# ---------------------------------------------------------------- datas

def e_dia_util(data):
    """Dia util = segunda a sexta. Feriado nao entra, por decisao."""
    return data.weekday() < 5


def proximo_dia_util(data):
    """Primeiro dia util DEPOIS de `data` (nunca a propria data)."""
    data += dt.timedelta(days=1)
    while not e_dia_util(data):
        data += dt.timedelta(days=1)
    return data


def soma_dias_uteis(data, quantidade):
    """Avanca `quantidade` dias uteis a partir de `data`, sem conta-la."""
    for _ in range(quantidade):
        data = proximo_dia_util(data)
    return data


def subtrai_dias_uteis(data, quantidade):
    """Recua `quantidade` dias uteis a partir de `data`, sem conta-la."""
    for _ in range(quantidade):
        data -= dt.timedelta(days=1)
        while not e_dia_util(data):
            data -= dt.timedelta(days=1)
    return data


def para_data(valor):
    """Le a data da API em qualquer dos formatos observados."""
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    if not valor:
        return None
    texto = str(valor).strip()[:19]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def calcula_prazo(data_disponibilizacao, dias):
    """Aplica a contagem vigente. Devolve as quatro datas do fluxo."""
    publicacao = proximo_dia_util(data_disponibilizacao)
    inicio = proximo_dia_util(publicacao)
    passos = dias - 1 if INICIO_CONTA_COMO_DIA_1 else dias
    final = soma_dias_uteis(inicio, passos)
    return {
        "publicacao": publicacao,
        "inicio": inicio,
        "prazo_final": final,
        "prazo_escritorio": subtrai_dias_uteis(final, FOLGA_ESCRITORIO),
    }


# ---------------------------------------------------------- classificacao

def e_trabalhista(sigla_tribunal):
    sigla = (sigla_tribunal or "").strip().upper()
    return sigla.startswith("TRT") or sigla == "TST"


def prioridade_por_dias(dias):
    if dias <= 5:
        return URGENTE
    if dias <= 15:
        return ALTA
    return MEDIA


def classifica(item):
    """Aplica as seis regras, na ordem. A primeira que casar decide.

    Recebe um item cru do DJEN e devolve a classificacao, sem alterar o item.
    """
    texto = limpa_texto(item.get("texto"))
    tribunal = item.get("siglaTribunal") or ""
    disponibilizacao = para_data(item.get("data_disponibilizacao"))

    base = {
        "prioridade": MEDIA,
        "dias": None,
        "publicacao": None,
        "inicio": None,
        "prazo_final": None,
        "prazo_escritorio": None,
        "regra_aplicada": "",
        "observacao": "",
    }

    # Regra 1 - sem teor
    if not texto:
        base.update(prioridade=SIGILO, regra_aplicada="Sem teor na API pública",
                    observacao="sem teor disponível na API pública, possível sigilo")
        return base

    achou = RX_DIAS.search(texto)

    # Regra 3 - trabalhista com prazo: nao calcula, por decisao
    if achou and e_trabalhista(tribunal):
        base.update(prioridade=MEDIA, dias=int(achou.group(1)),
                    regra_aplicada="Justiça do Trabalho — prazo não calculado (decisão de 27/10/2026)",
                    observacao="regra CLT — requer conferência manual")
        return base

    # Regra 2 - prazo em dias, fora da Justica do Trabalho
    if achou:
        dias = int(achou.group(1))
        base.update(prioridade=prioridade_por_dias(dias), dias=dias,
                    regra_aplicada=f"Prazo de {dias} dias úteis identificado no teor")
        if disponibilizacao:
            base.update(calcula_prazo(disponibilizacao, dias))
        else:
            base["observacao"] = "data de disponibilização ausente — prazo não calculado"
        return base

    # Regra 4 - audiencia com data fixa
    if RX_AUDIENCIA.search(texto):
        data = RX_DATA_BR.search(texto)
        if data:
            dia, mes, ano = (int(x) for x in data.groups())
            try:
                base.update(prioridade=MEDIA, prazo_final=dt.date(ano, mes, dia),
                            regra_aplicada="Data fixa de audiência",
                            observacao="data fixa de audiência")
                return base
            except ValueError:
                pass

    # Regra 5 - mero andamento
    plano = _sem_acento(texto)
    if any(termo in plano for termo in TERMOS_ANDAMENTO):
        base.update(prioridade=BAIXA, regra_aplicada="Mero andamento",
                    observacao="sem prazo para o escritório")
        return base

    # Regra 6 - resto
    base.update(prioridade=MEDIA, regra_aplicada="Nenhum prazo identificado",
                observacao="nenhum prazo identificado automaticamente — "
                           "requer leitura manual do teor")
    return base


def classifica_lote(itens):
    """Classifica e deduplica por `id`, preservando a ordem de chegada."""
    vistos = set()
    saida = []
    for item in itens:
        # `or` nao serve aqui: id igual a 0 e valido e seria tratado como ausente
        chave = item.get("id")
        if chave is None:
            chave = item.get("hash")
        if chave is not None and chave in vistos:
            continue
        if chave is not None:
            vistos.add(chave)
        registro = dict(item)
        registro["classificacao"] = classifica(item)
        saida.append(registro)
    return saida


def ordena_por_prioridade(registros):
    posicao = {p: i for i, p in enumerate(ORDEM_PRIORIDADE)}
    return sorted(registros,
                  key=lambda r: (posicao.get(r["classificacao"]["prioridade"], 99),
                                 r["classificacao"]["prazo_final"] or dt.date.max))
