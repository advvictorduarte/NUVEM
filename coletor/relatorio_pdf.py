"""Relatorio diario em PDF, no formato de cards ja validado com o advogado."""
import datetime as dt

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from . import regras

AVISO = (
    "Classificação e prazos gerados automaticamente por heurística de texto. "
    "<b>A validação humana é obrigatória.</b> O cálculo não considera feriados "
    "forenses, feriados locais nem o recesso de 20/12 a 20/01. Publicações do "
    "TRT e do TST <b>não têm prazo calculado</b> e dependem de conferência "
    "manual. Todo prazo aqui nasce não confirmado."
)


def _texto(valor):
    return "" if valor is None else str(valor)


def _partes(item):
    destinatarios = item.get("destinatarios") or []
    nomes = []
    for d in destinatarios:
        if isinstance(d, dict):
            nomes.append(d.get("nome") or d.get("nomeParte") or "")
        else:
            nomes.append(str(d))
    nomes = [n for n in nomes if n]
    if not nomes:
        return "—"
    if len(nomes) > 3:
        return "; ".join(nomes[:3]) + f" e mais {len(nomes) - 3}"
    return "; ".join(nomes)


def junta(*partes, sep=" · "):
    """Junta os pedacos nao vazios; evita separador solto."""
    return sep.join(str(x).strip() for x in partes if x and str(x).strip()) or "—"


def _data_br(valor):
    if isinstance(valor, dt.date):
        return valor.strftime("%d/%m/%Y")
    return "—"


def sugestao(classificacao):
    """Sugestao de medida, derivada da regra. Sempre editavel pelo advogado."""
    p = classificacao["prioridade"]
    if p == regras.SIGILO:
        return "Consultar o teor no sistema do tribunal e classificar manualmente"
    if classificacao["dias"] and classificacao["prazo_final"] is None:
        return ("Conferir a contagem manualmente e lançar o prazo "
                f"({classificacao['dias']} dias)")
    if classificacao["prazo_final"] and classificacao["observacao"] == "data fixa de audiência":
        return "Confirmar a pauta e agendar preparação da audiência"
    if classificacao["prazo_final"]:
        return "Protocolar a manifestação até o prazo do escritório"
    if p == regras.BAIXA:
        return "Apenas ciência"
    return "Ler o teor e decidir a medida"


def gera(registros, coleta_resumo, advogado, oab, caminho, data=None):
    data = data or dt.date.today()
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("corpo", parent=estilos["Normal"], fontSize=8.5,
                            leading=11, alignment=TA_JUSTIFY)
    rotulo = ParagraphStyle("rotulo", parent=normal, fontSize=7.5,
                            textColor=colors.HexColor("#555555"))
    vermelho = ParagraphStyle("vermelho", parent=normal, fontSize=9,
                              textColor=colors.HexColor("#C00000"))
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=16)
    aviso = ParagraphStyle("aviso", parent=normal, fontSize=8,
                           textColor=colors.HexColor("#C00000"),
                           fontName="Helvetica-Oblique")

    doc = SimpleDocTemplate(caminho, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm,
                            title="Relatório Diário de Publicações e Prazos")
    fluxo = [Paragraph("Relatório Diário de Publicações e Prazos", titulo),
             Paragraph(f"{advogado} — OAB {oab} — {data.strftime('%d/%m/%Y')}",
                       estilos["Normal"]),
             Spacer(1, 4*mm)]

    # --- Estado da coleta, antes de qualquer numero ---
    if not coleta_resumo["completa"]:
        fluxo += [Paragraph(
            f"<b>ATENÇÃO: a coleta falhou.</b> {coleta_resumo['erro']}<br/>"
            "Os números abaixo <b>não</b> representam o período. "
            "Não é possível afirmar que não houve publicações.", aviso),
            Spacer(1, 4*mm)]
    elif not registros:
        fluxo += [Paragraph(
            "Nenhuma publicação encontrada no período consultado "
            f"({coleta_resumo['periodo']['inicio']} a "
            f"{coleta_resumo['periodo']['fim']}). A consulta foi concluída "
            "com sucesso.", normal), Spacer(1, 4*mm)]

    # --- Resumo por prioridade ---
    contagem = {p: 0 for p in regras.ORDEM_PRIORIDADE}
    for r in registros:
        contagem[r["classificacao"]["prioridade"]] += 1
    linhas = [["Prioridade", "Publicações"]]
    estilo_resumo = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]
    for i, p in enumerate(regras.ORDEM_PRIORIDADE, start=1):
        linhas.append([p, str(contagem[p])])
        estilo_resumo += [
            ("BACKGROUND", (0, i), (0, i), colors.HexColor("#" + regras.CORES[p])),
            ("TEXTCOLOR", (0, i), (0, i), colors.white),
        ]
    linhas.append(["Total", str(len(registros))])
    tabela = Table(linhas, colWidths=[60*mm, 25*mm])
    tabela.setStyle(TableStyle(estilo_resumo))
    fluxo += [tabela, Spacer(1, 4*mm), Paragraph(AVISO, aviso), Spacer(1, 6*mm)]

    # --- Cards, agrupados por prioridade ---
    for prioridade in regras.ORDEM_PRIORIDADE:
        do_grupo = [r for r in registros
                    if r["classificacao"]["prioridade"] == prioridade]
        if not do_grupo:
            continue
        cor = colors.HexColor("#" + regras.CORES[prioridade])
        cabecalho = Table([[Paragraph(
            f'<font color="white"><b>{prioridade} — {len(do_grupo)}</b></font>',
            normal)]], colWidths=[180*mm])
        cabecalho.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cor),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
        fluxo += [cabecalho, Spacer(1, 2*mm)]
        for r in do_grupo:
            fluxo.append(_card(r, cor, normal, rotulo, vermelho))
            fluxo.append(Spacer(1, 3*mm))

    doc.build(fluxo)
    return caminho


def _card(registro, cor, normal, rotulo, vermelho):
    c = registro["classificacao"]
    teor = regras.limpa_texto(registro.get("texto"))
    if len(teor) > 700:
        teor = teor[:700] + " […]"

    def par(rot, valor, estilo=None):
        return [Paragraph(rot, rotulo), Paragraph(_texto(valor), estilo or normal)]

    datas = (f"Disponibilização: {_data_br(regras.para_data(registro.get('data_disponibilizacao')))} · "
             f"Publicação: {_data_br(c['publicacao'])} · "
             f"Início: {_data_br(c['inicio'])}")
    if c["prazo_final"]:
        prazo = (f"<b>Prazo final: {_data_br(c['prazo_final'])}</b>")
        if c["prazo_escritorio"]:
            prazo += f" · Prazo do escritório: <b>{_data_br(c['prazo_escritorio'])}</b>"
    else:
        prazo = "<b>Prazo não calculado</b> — " + (c["observacao"] or "ver regra aplicada")

    linhas = [
        par("Processo", registro.get("numeroprocessocommascara")
            or registro.get("numero_processo") or "—"),
        par("Cliente / partes", _partes(registro)),
        par("Tribunal / órgão", junta(registro.get("siglaTribunal"),
                                      registro.get("nomeOrgao"), sep=" — ")),
        par("Tipo de ato", junta(registro.get("tipoComunicacao"),
                                 registro.get("tipoDocumento"))),
        par("Teor", teor or "—"),
        par("Datas", datas),
        par("Prazo", prazo, vermelho),
        par("Regra aplicada", c["regra_aplicada"] or "—"),
        par("Sugestão de medida", sugestao(c)),
    ]
    tabela = Table(linhas, colWidths=[32*mm, 148*mm])
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (0, 0), (0, -1), 2, cor),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return KeepTogether(tabela)
