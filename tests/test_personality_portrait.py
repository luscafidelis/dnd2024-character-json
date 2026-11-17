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
        self.assertIsNone(gs.resolver_retrato(personagem_minimo(), "x/char.json"))

    def test_caminho_relativo_ao_json(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho_json = Path(pasta) / "char.json"
            resolvido = gs.resolver_retrato(personagem_minimo(portrait="img/r.png"), caminho_json)
            self.assertEqual(resolvido, caminho_json.resolve().parent / "img" / "r.png")

    def test_caminho_absoluto_e_mantido(self):
        absoluto = Path(tempfile.gettempdir()).resolve() / "r.png"
        resolvido = gs.resolver_retrato(personagem_minimo(portrait=str(absoluto)), "x/char.json")
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
                      if w.field_name == gs.CAMPO_RETRATO)
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

    def test_retrato_ilegivel_gera_aviso_e_ficha_sai_sem_ele(self):
        with tempfile.TemporaryDirectory() as pasta:
            ruim = Path(pasta) / "ruim.png"
            ruim.write_bytes(b"isto nao e uma imagem")
            saida = Path(pasta) / "saida.pdf"
            campos, checks = gs.compute_fields(personagem_minimo())
            avisos = gs.fill_pdf(str(TEMPLATE), str(saida), campos, checks, ruim)
            self.assertEqual(len(avisos), 1)
            self.assertIn("portrait could not be drawn", avisos[0])
            self.assertTrue(saida.is_file() and saida.stat().st_size > 0)

    def test_sem_retrato_fill_pdf_nao_gera_avisos(self):
        with tempfile.TemporaryDirectory() as pasta:
            campos, checks = gs.compute_fields(personagem_minimo())
            self.assertEqual(gs.fill_pdf(str(TEMPLATE), str(Path(pasta) / "s.pdf"),
                                         campos, checks), [])


class TestePreparacaoDoRetrato(unittest.TestCase):
    def test_retrato_inexistente_vira_aviso_e_e_ignorado(self):
        char = personagem_minimo(portrait="nao-existe.png")
        caminho, avisos = gs.preparar_retrato(char, RAIZ / "characters" / "x.json")
        self.assertIsNone(caminho)
        self.assertEqual(len(avisos), 1)
        self.assertIn("portrait not found", avisos[0])

    def test_retrato_existente_e_repassado_sem_aviso(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "r.png").write_bytes(b"x")
            caminho, avisos = gs.preparar_retrato(personagem_minimo(portrait="r.png"),
                                                  Path(pasta) / "c.json")
            self.assertEqual(caminho, (Path(pasta) / "r.png").resolve())
            self.assertEqual(avisos, [])

    def test_sem_retrato_nao_gera_aviso(self):
        self.assertEqual(gs.preparar_retrato(personagem_minimo(), "x.json"), (None, []))


class TesteSemPyMuPDF(unittest.TestCase):
    def test_retrato_vira_aviso_quando_fitz_nao_existe(self):
        from unittest import mock
        with mock.patch.dict(sys.modules, {"fitz": None}):
            dados, avisos = gs._flatten_bytes(b"%PDF-1.4", "r.png")
        self.assertEqual(dados, b"%PDF-1.4")
        self.assertEqual(avisos, ["PyMuPDF not installed; portrait skipped"])


if __name__ == "__main__":
    unittest.main()
