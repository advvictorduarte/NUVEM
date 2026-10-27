"""Testes das regras de prazo e classificacao (CLAUDE.md, Forma de trabalhar).

Os casos de contagem usam datas reais do controle de prazos do escritorio.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coletor import regras  # noqa: E402

D = dt.date


class TestDiasUteis(unittest.TestCase):
    def test_sabado_e_domingo_nao_sao_uteis(self):
        self.assertTrue(regras.e_dia_util(D(2026, 10, 16)))   # sexta
        self.assertFalse(regras.e_dia_util(D(2026, 10, 17)))  # sabado
        self.assertFalse(regras.e_dia_util(D(2026, 10, 18)))  # domingo
        self.assertTrue(regras.e_dia_util(D(2026, 10, 19)))   # segunda

    def test_proximo_dia_util_pula_o_fim_de_semana(self):
        # sexta -> segunda
        self.assertEqual(regras.proximo_dia_util(D(2026, 10, 16)), D(2026, 10, 19))
        # quinta -> sexta
        self.assertEqual(regras.proximo_dia_util(D(2026, 10, 15)), D(2026, 10, 16))

    def test_proximo_dia_util_nunca_devolve_a_propria_data(self):
        self.assertEqual(regras.proximo_dia_util(D(2026, 10, 19)), D(2026, 10, 20))

    def test_subtrai_dias_uteis_pula_o_fim_de_semana(self):
        # 3 dias uteis antes de sexta 23/10 -> 22, 21, 20
        self.assertEqual(regras.subtrai_dias_uteis(D(2026, 10, 23), 3), D(2026, 10, 20))
        # 3 dias uteis antes de segunda 19/10 -> 16, 15, 14
        self.assertEqual(regras.subtrai_dias_uteis(D(2026, 10, 19), 3), D(2026, 10, 14))


class TestContagemDePrazo(unittest.TestCase):
    def test_caso_real_do_escritorio(self):
        """Disponibilizado 15/10/2026, prazo de 5 dias.

        Caso conferido no controle de prazos: publicacao 16/10,
        inicio 19/10, prazo final 23/10, prazo do escritorio 20/10.
        """
        r = regras.calcula_prazo(D(2026, 10, 15), 5)
        self.assertEqual(r["publicacao"], D(2026, 10, 16))
        self.assertEqual(r["inicio"], D(2026, 10, 19))
        self.assertEqual(r["prazo_final"], D(2026, 10, 23))
        self.assertEqual(r["prazo_escritorio"], D(2026, 10, 20))

    def test_disponibilizacao_na_sexta_publica_na_segunda(self):
        r = regras.calcula_prazo(D(2026, 10, 16), 5)
        self.assertEqual(r["publicacao"], D(2026, 10, 19))
        self.assertEqual(r["inicio"], D(2026, 10, 20))

    def test_prazo_de_um_dia_vence_no_proprio_inicio(self):
        r = regras.calcula_prazo(D(2026, 10, 15), 1)
        self.assertEqual(r["inicio"], D(2026, 10, 19))
        self.assertEqual(r["prazo_final"], D(2026, 10, 19))

    def test_nenhuma_data_do_fluxo_cai_em_fim_de_semana(self):
        for dia in range(1, 29):
            for n in (1, 2, 5, 10, 15, 30):
                r = regras.calcula_prazo(D(2026, 10, dia), n)
                for chave in ("publicacao", "inicio", "prazo_final",
                              "prazo_escritorio"):
                    self.assertTrue(regras.e_dia_util(r[chave]),
                                    f"{chave} caiu em fim de semana: "
                                    f"disp {dia}/10, N={n}, {r[chave]}")

    def test_prazo_final_nunca_e_anterior_ao_inicio(self):
        for n in range(1, 61):
            r = regras.calcula_prazo(D(2026, 10, 15), n)
            self.assertGreaterEqual(r["prazo_final"], r["inicio"])


class TestClassificacao(unittest.TestCase):
    def item(self, **kw):
        base = {"id": 1, "texto": "", "siglaTribunal": "TJRJ",
                "data_disponibilizacao": "2026-10-15"}
        base.update(kw)
        return base

    def test_texto_vazio_vira_sigilo_sem_prazo(self):
        c = regras.classifica(self.item(texto=""))
        self.assertEqual(c["prioridade"], regras.SIGILO)
        self.assertIsNone(c["prazo_final"])

    def test_trabalhista_nao_tem_prazo_calculado(self):
        for sigla in ("TRT1", "TRT2", "TST"):
            c = regras.classifica(self.item(
                texto="Manifeste-se em 5 dias.", siglaTribunal=sigla))
            self.assertEqual(c["prioridade"], regras.MEDIA, sigla)
            self.assertIsNone(c["prazo_final"], sigla)
            self.assertEqual(c["dias"], 5, sigla)
            self.assertIn("conferência manual", c["observacao"])

    def test_nao_trabalhista_tem_prazo_calculado(self):
        c = regras.classifica(self.item(
            texto="Manifeste-se em 5 dias.", siglaTribunal="TJRJ"))
        self.assertEqual(c["prioridade"], regras.URGENTE)
        self.assertEqual(c["prazo_final"], D(2026, 10, 23))

    def test_faixas_de_prioridade(self):
        casos = [(1, regras.URGENTE), (5, regras.URGENTE), (6, regras.ALTA),
                 (15, regras.ALTA), (16, regras.MEDIA), (30, regras.MEDIA)]
        for dias, esperado in casos:
            c = regras.classifica(self.item(texto=f"prazo de {dias} dias"))
            self.assertEqual(c["prioridade"], esperado, f"N={dias}")

    def test_audiencia_com_data_fixa(self):
        c = regras.classifica(self.item(
            texto="Fica designada audiência para 03/12/2026 às 14h."))
        self.assertEqual(c["prioridade"], regras.MEDIA)
        self.assertEqual(c["prazo_final"], D(2026, 12, 3))

    def test_mero_andamento_vira_baixa(self):
        # Os termos sao casados literalmente, como na regra vigente
        for texto in ("Processo remetido ao arquivamento.",
                      "Certifico que a conta está sem saldo.",
                      "Lista de distribuição publicada.",
                      "Processo distribuído por sorteio."):
            c = regras.classifica(self.item(texto=texto))
            self.assertEqual(c["prioridade"], regras.BAIXA, texto)


    def test_sinonimo_de_andamento_nao_e_reconhecido(self):
        """Limitacao conhecida: a regra casa termos literais, nao sinonimos."""
        c = regras.classifica(self.item(texto="Certifico que não há saldo."))
        self.assertEqual(c["prioridade"], regras.MEDIA)

    def test_em_ate_n_dias_nao_e_reconhecido(self):
        """Limitação conhecida, vista em publicação real do TRT1 em 26/10/2026.

        "em até 5 dias" não casa com a expressão vigente, que exige
        "em N dias" ou "prazo de N dias". O prazo passa despercebido.
        """
        c = regras.classifica(self.item(
            texto="Intimem-se as partes a adequar seus cálculos em até 5 dias."))
        self.assertIsNone(c["dias"])
        self.assertIn("leitura manual", c["observacao"])

    def test_prazo_em_horas_nao_e_reconhecido(self):
        """Limitação conhecida: pauta do TST fala em "48 horas", não em dias."""
        c = regras.classifica(self.item(
            texto="Pedido de destaque até 48 horas antes do início da sessão."))
        self.assertIsNone(c["dias"])

    def test_html_do_teor_nao_atrapalha_a_busca_do_prazo(self):
        c = regras.classifica(self.item(
            texto="Manifeste-se em 5 dias.<br><br>Intimado(s)<br> - FULANO"))
        self.assertEqual(c["dias"], 5)

    def test_sem_regra_vira_media_com_aviso(self):
        c = regras.classifica(self.item(texto="Vistos. Cumpra-se."))
        self.assertEqual(c["prioridade"], regras.MEDIA)
        self.assertIn("leitura manual", c["observacao"])

    def test_prazo_sem_data_de_disponibilizacao_nao_inventa(self):
        c = regras.classifica(self.item(texto="em 5 dias",
                                        data_disponibilizacao=None))
        self.assertIsNone(c["prazo_final"])
        self.assertIn("ausente", c["observacao"])


class TestDeduplicacao(unittest.TestCase):
    def test_mesmo_id_nao_entra_duas_vezes(self):
        itens = [{"id": 10, "texto": "a", "siglaTribunal": "TJRJ"},
                 {"id": 10, "texto": "a", "siglaTribunal": "TJRJ"},
                 {"id": 11, "texto": "b", "siglaTribunal": "TJRJ"}]
        self.assertEqual(len(regras.classifica_lote(itens)), 2)

    def test_rodar_duas_vezes_da_o_mesmo_resultado(self):
        itens = [{"id": i, "texto": "em 5 dias", "siglaTribunal": "TJRJ",
                  "data_disponibilizacao": "2026-10-15"} for i in range(5)]
        a = regras.classifica_lote(itens)
        b = regras.classifica_lote(itens + itens)
        self.assertEqual(len(a), len(b))

    def test_item_sem_id_nao_e_descartado(self):
        itens = [{"texto": "x", "siglaTribunal": "TJRJ"},
                 {"texto": "y", "siglaTribunal": "TJRJ"}]
        self.assertEqual(len(regras.classifica_lote(itens)), 2)


class TestOrdenacao(unittest.TestCase):
    def test_ordem_das_prioridades(self):
        itens = [{"id": 1, "texto": "Vistos.", "siglaTribunal": "TJRJ"},
                 {"id": 2, "texto": "", "siglaTribunal": "TJRJ"},
                 {"id": 3, "texto": "arquivamento", "siglaTribunal": "TJRJ"},
                 {"id": 4, "texto": "em 3 dias", "siglaTribunal": "TJRJ",
                  "data_disponibilizacao": "2026-10-15"}]
        ordenados = regras.ordena_por_prioridade(regras.classifica_lote(itens))
        self.assertEqual([r["classificacao"]["prioridade"] for r in ordenados],
                         [regras.SIGILO, regras.URGENTE, regras.MEDIA, regras.BAIXA])


if __name__ == "__main__":
    unittest.main(verbosity=2)
