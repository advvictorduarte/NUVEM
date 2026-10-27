"""Monta `coletor/gerar_relatorio.py` a partir do pacote `coletor`.

O arquivo unico existe para a tarefa agendada diaria, que baixa um unico
arquivo do Supabase e executa, sem instalar o pacote. A fonte da verdade
continua sendo o pacote: altere la e rode este script.

    python scripts/monta_gerador.py
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODULOS = ["coletor/regras.py", "coletor/relatorio_pdf.py",
           "coletor/relatorio_xlsx.py"]


def corpo(caminho):
    """Devolve o modulo sem a docstring e sem nenhum import."""
    texto = (RAIZ / caminho).read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    linhas = texto.splitlines(keepends=True)
    remover = set()
    for no in arvore.body:
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            remover.update(range(no.lineno - 1, no.end_lineno))
        elif (isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
              and isinstance(no.value.value, str) and no.lineno == 1):
            remover.update(range(no.lineno - 1, no.end_lineno))
    return "".join(l for i, l in enumerate(linhas)
                   if i not in remover).strip("\n") + "\n"


def main():
    juntado = "\n\n".join(corpo(m) for m in MODULOS).replace("regras.", "")
    # Num arquivo so, as duas funcoes `gera` precisam de nomes distintos
    for marca, nome in (("estilos", "gera_pdf"), ("wb = Workbook()", "gera_xlsx")):
        juntado = juntado.replace(
            "def gera(registros, coleta_resumo, advogado, oab, caminho, data=None):"
            f"\n    data = data or dt.date.today()\n    {marca}",
            f"def {nome}(registros, coleta_resumo, advogado, oab, caminho, data=None):"
            f"\n    data = data or dt.date.today()\n    {marca}")
    destino = RAIZ / "coletor" / "gerar_relatorio.py"
    cabecalho = (RAIZ / "scripts" / "gerador_cabecalho.txt").read_text(encoding="utf-8")
    rodape = (RAIZ / "scripts" / "gerador_rodape.txt").read_text(encoding="utf-8")
    destino.write_text(cabecalho + juntado + rodape, encoding="utf-8")
    ast.parse(destino.read_text(encoding="utf-8"))
    print(f"gerado: {destino} ({len(destino.read_text(encoding='utf-8').splitlines())} linhas)")


if __name__ == "__main__":
    main()
