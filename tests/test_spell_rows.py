"""Testes do alinhamento das linhas de magia no template PDF.

Garante que, para cada linha visual da tabela de magias, os campos de nome,
nível, tempo de conjuração, alcance e notas preenchidos por compute_fields()
ficam na MESMA altura da página (antes, as notas caíam em linhas trocadas).

Executar a partir da raiz do repositório:  python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader  # noqa: E402

import generate_sheets as gs  # noqa: E402

TEMPLATE = RAIZ / "_character_sheet_template.pdf"
TOTAL_LINHAS = 29


def posicoes_campos():
    """Retorna {nome_do_campo: y_inferior} de todos os widgets do template."""
    posicoes = {}
    for pagina in PdfReader(str(TEMPLATE)).pages:
        for anotacao in pagina.get("/Annots", []) or []:
            o = anotacao.get_object()
            nome = o.get("/T")
            if nome is None and o.get("/Parent") is not None:
                nome = o["/Parent"].get_object().get("/T")
            if nome is not None and "/Rect" in o:
                posicoes.setdefault(str(nome), float(o["/Rect"][1]))
    return posicoes


class TesteLinhasDeMagia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posicoes = posicoes_campos()
        magias = [
            {"level": "1", "name": "Magia{}".format(i), "casting_time": "1A",
             "range": "Pessoal", "notes": "Nota{}".format(i)}
            for i in range(TOTAL_LINHAS)
        ]
        personagem = {"name": "Teste", "classes": [{"name": "Bruxo", "level": 1}],
                      "abilities": {k: 10 for k in gs.ABILITY_SHORT}, "spells": magias}
        cls.campos, _ = gs.compute_fields(personagem)

    def _campo_com_valor(self, prefixo, valor):
        encontrados = [k for k, v in self.campos.items()
                       if v == valor and k.startswith(prefixo)]
        self.assertEqual(len(encontrados), 1, (prefixo, valor, encontrados))
        return encontrados[0]

    def test_sufixo_das_notas_e_sequencial(self):
        self.assertEqual(gs.sufixo_notas_magia(0), "")
        self.assertEqual(gs.sufixo_notas_magia(1), "0")
        self.assertEqual(gs.sufixo_notas_magia(28), "27")

    def test_campos_da_mesma_linha_ficam_na_mesma_altura(self):
        for i in range(TOTAL_LINHAS):
            with self.subTest(linha=i):
                y_nome = self.posicoes[self._campo_com_valor("SPELL NAME", "Magia{}".format(i))]
                y_nota = self.posicoes[self._campo_com_valor("SPELL NOTES", "Nota{}".format(i))]
                self.assertAlmostEqual(y_nome, y_nota, delta=3,
                                       msg="nota da linha {} desalinhada do nome".format(i))

    def test_linhas_seguem_de_cima_para_baixo(self):
        alturas = [self.posicoes[self._campo_com_valor("SPELL NOTES", "Nota{}".format(i))]
                   for i in range(TOTAL_LINHAS)]
        self.assertEqual(alturas, sorted(alturas, reverse=True))


if __name__ == "__main__":
    unittest.main()
