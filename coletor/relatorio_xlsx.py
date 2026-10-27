"""Planilha diaria de controle de prazos.

Datas sao datas de verdade (datetime.date), nao texto, e as colunas
calculadas usam formula WORKDAY, para o advogado poder mexer no numero de
dias e ver o prazo se recalcular sozinho.
"""
import datetime as dt

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import regras
from .relatorio_pdf import _partes, junta, sugestao

COLUNAS = [
    ("Prioridade", 16), ("Processo", 24), ("Cliente/Parte", 34),
    ("Tribunal/Órgão", 30), ("Tipo de ato", 22), ("Teor", 60),
    ("Disponibilização", 15), ("Publicação", 13), ("Início do prazo", 15),
    ("Dias úteis do prazo", 12), ("Prazo final", 13),
    ("Prazo do escritório", 15), ("Regra aplicada", 38),
    ("Sugestão de medida", 34),
]

LEIAME = [
    ("Como ler esta planilha", True),
    ("", False),
    ("Gerada automaticamente a partir do DJEN (API pública do CNJ).", False),
    ("", False),
    ("O que ela NÃO faz:", True),
    ("1. Não considera feriados forenses, feriados locais nem o recesso de 20/12 a 20/01.", False),
    ("2. Não calcula prazo de TRT nem TST. Esses itens vêm sem prazo e precisam de conferência manual.", False),
    ("3. Identifica o número de dias por expressão de texto: não pega \"15 (quinze) dias\" nem prazo citado por artigo de lei.", False),
    ("4. Não guarda histórico: cada dia gera um arquivo novo.", False),
    ("", False),
    ("Toda classificação e todo prazo aqui são sugestões automáticas.", True),
    ("A validação é do advogado. Nenhum prazo nasce confirmado.", True),
    ("", False),
    ("As colunas Publicação, Início, Prazo final e Prazo do escritório usam fórmula WORKDAY:", False),
    ("mudando a coluna \"Dias úteis do prazo\", as datas se recalculam sozinhas.", False),
    ("WORKDAY considera só segunda a sexta — nenhum feriado é informado a ela.", False),
]


def gera(registros, coleta_resumo, advogado, oab, caminho, data=None):
    data = data or dt.date.today()
    wb = Workbook()

    # --- Aba Leia-me ---
    ws = wb.active
    ws.title = "Leia-me"
    ws.column_dimensions["A"].width = 115
    ws["A1"] = f"Controle de prazos — {advogado} — OAB {oab} — {data.strftime('%d/%m/%Y')}"
    ws["A1"].font = Font(bold=True, size=13)
    linha = 3
    if not coleta_resumo["completa"]:
        ws[f"A{linha}"] = f"ATENÇÃO: a coleta falhou. {coleta_resumo['erro']}"
        ws[f"A{linha}"].font = Font(bold=True, color="C00000")
        ws[f"A{linha + 1}"] = ("Os dados abaixo não representam o período. "
                               "Não é possível afirmar que não houve publicações.")
        ws[f"A{linha + 1}"].font = Font(color="C00000")
        linha += 3
    for texto, negrito in LEIAME:
        ws[f"A{linha}"] = texto
        ws[f"A{linha}"].font = Font(bold=negrito)
        ws[f"A{linha}"].alignment = Alignment(wrap_text=True)
        linha += 1

    # --- Aba de dados ---
    ws = wb.create_sheet("Prazos")
    for i, (nome, largura) in enumerate(COLUNAS, start=1):
        celula = ws.cell(row=1, column=i, value=nome)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="404040")
        celula.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.freeze_panes = "A2"

    for i, registro in enumerate(regras.ordena_por_prioridade(registros), start=2):
        c = registro["classificacao"]
        disponibilizacao = regras.para_data(registro.get("data_disponibilizacao"))
        teor = (regras.limpa_texto(registro.get("texto"))
                .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))

        ws.cell(row=i, column=1, value=c["prioridade"]).fill = PatternFill(
            "solid", fgColor=regras.CORES[c["prioridade"]])
        ws.cell(row=i, column=1).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=i, column=2, value=registro.get("numeroprocessocommascara")
                or registro.get("numero_processo") or "")
        ws.cell(row=i, column=3, value=_partes(registro))
        ws.cell(row=i, column=4, value=junta(registro.get("siglaTribunal"),
                                             registro.get("nomeOrgao"), sep=" — "))
        ws.cell(row=i, column=5, value=junta(registro.get("tipoComunicacao"),
                                             registro.get("tipoDocumento")))
        ws.cell(row=i, column=6, value=teor[:2000])
        ws.cell(row=i, column=7, value=disponibilizacao).number_format = "DD/MM/YYYY"
        ws.cell(row=i, column=10, value=c["dias"])

        # As datas calculadas saem como formula, para recalcularem sozinhas.
        # Nos casos sem prazo (sigilo, trabalhista, mero andamento) ficam vazias.
        if disponibilizacao and c["dias"] and c["prazo_final"]:
            passos = c["dias"] - 1 if regras.INICIO_CONTA_COMO_DIA_1 else c["dias"]
            ws.cell(row=i, column=8, value=f"=WORKDAY(G{i},1)")
            ws.cell(row=i, column=9, value=f"=WORKDAY(H{i},1)")
            ws.cell(row=i, column=11, value=f"=WORKDAY(I{i},{passos})")
            ws.cell(row=i, column=12,
                    value=f"=WORKDAY(K{i},-{regras.FOLGA_ESCRITORIO})")
            for coluna in (8, 9, 11, 12):
                ws.cell(row=i, column=coluna).number_format = "DD/MM/YYYY"
            ws.cell(row=i, column=12).font = Font(bold=True, color="C00000")
        elif c["prazo_final"]:  # data fixa de audiencia: valor, nao formula
            ws.cell(row=i, column=11, value=c["prazo_final"]).number_format = "DD/MM/YYYY"

        ws.cell(row=i, column=13, value=c["regra_aplicada"]
                + (f" — {c['observacao']}" if c["observacao"] else ""))
        ws.cell(row=i, column=14, value=sugestao(c))
        for coluna in (3, 4, 5, 6, 13, 14):
            ws.cell(row=i, column=coluna).alignment = Alignment(
                wrap_text=True, vertical="top")

    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS))}{max(1, len(registros) + 1)}"
    wb.save(caminho)
    return caminho
