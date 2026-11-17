"""Testes dos campos opcionais da spec 1.1.0: appearance, backstory e portrait.

Executar a partir da raiz do repositório:  python -m unittest discover tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import generate_sheets as gs  # noqa: E402

TEMPLATE = RAIZ / "_character_sheet_template.pdf"


def personagem_minimo(**extras):
    base = {"name": "Teste", "classes": [{"name": "Bruxo", "level": 1}],
            "abilities": {k: 10 for k in gs.ABILITY_SHORT}}
    base.update(extras)
    return base


class TesteTextoDePersonalidade(unittest.TestCase):
    def test_quadro_recebe_so_a_personalidade(self):
        char = personagem_minimo(personality="P", appearance="A", backstory="H")
        campos, _ = gs.compute_fields(char)
        self.assertEqual(campos["PERSONALITY"], "P")

    def test_aparencia_e_historia_nao_sao_impressas(self):
        campos, _ = gs.compute_fields(personagem_minimo(appearance="A", backstory="H"))
        self.assertEqual(campos["PERSONALITY"], "")
        self.assertNotIn("A", campos.values())
        self.assertNotIn("H", campos.values())


class TesteResolucaoDoRetrato(unittest.TestCase):
    def test_sem_retrato_retorna_none(self):
        self.assertIsNone(gs.resolve_portrait(personagem_minimo(), "x/char.json"))

    def test_caminho_relativo_ao_json(self):
        with tempfile.TemporaryDirectory() as pasta:
            json_path = Path(pasta) / "char.json"
            resolvido = gs.resolve_portrait(personagem_minimo(portrait="img/r.png"), json_path)
            self.assertEqual(resolvido, json_path.resolve().parent / "img" / "r.png")

    def test_caminho_absoluto_e_mantido(self):
        absoluto = Path(tempfile.gettempdir()).resolve() / "r.png"
        resolvido = gs.resolve_portrait(personagem_minimo(portrait=str(absoluto)), "x/char.json")
        self.assertEqual(resolvido, absoluto)


class TesteRetratoNoPdf(unittest.TestCase):
    def setUp(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("PyMuPDF não instalado")

    def _gerar_pagina2(self, pasta, nome, retrato):
        """Gera o PDF e devolve [(largura, altura, retângulo)] das imagens da página 2."""
        import fitz
        saida = Path(pasta) / nome
        campos, checks = gs.compute_fields(personagem_minimo())
        gs.fill_pdf(str(TEMPLATE), str(saida), campos, checks, retrato)
        doc = fitz.open(str(saida))
        try:
            pagina = doc[1]
            return [(img[2], img[3], ret) for img in pagina.get_images(full=True)
                    for ret in pagina.get_image_rects(img[0])]
        finally:
            doc.close()

    def test_imagem_e_inserida_dentro_do_quadro(self):
        import fitz
        modelo = fitz.open(str(TEMPLATE))
        quadro = next(w.rect for p in modelo for w in p.widgets()
                      if w.field_name == gs.PORTRAIT_FIELD)
        modelo.close()
        with tempfile.TemporaryDirectory() as pasta:
            png = Path(pasta) / "r.png"
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 60), False)
            pix.clear_with(200)
            pix.save(str(png))

            sem = self._gerar_pagina2(pasta, "sem.pdf", None)
            com = self._gerar_pagina2(pasta, "com.pdf", png)
            novas = [x for x in com if (x[0], x[1]) == (40, 60)]
            self.assertEqual(len(com), len(sem) + 1)
            self.assertEqual(len(novas), 1)
            area = novas[0][2]
            self.assertTrue(quadro.contains(area), (quadro, area))
            # proporção 40x60 preservada
            self.assertAlmostEqual(area.width / area.height, 40 / 60, places=2)

    def test_retrato_inexistente_gera_aviso_e_nao_quebra(self):
        char = personagem_minimo(portrait="nao-existe.png")
        caminho = gs.resolve_portrait(char, RAIZ / "characters" / "x.json")
        self.assertFalse(caminho.is_file())


if __name__ == "__main__":
    unittest.main()
