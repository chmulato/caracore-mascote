"""Testes da lista de modulos que precisa ir para o pacote (ressalva D6 da Alpha).

Sem build e sem PyInstaller: aqui so se confere o texto dos dois specs contra os
modulos que existem no codigo-fonte. A presenca fisica dentro do executavel se
prova na maquina de build com ``python packaging/verifica_pacote.py``.

O verificador e carregado pelo caminho do arquivo de proposito: ``packaging`` e
tambem o nome de um pacote instalado pelo pip, e esse e que ganha o ``import``.
"""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SPECS = (
    RAIZ / "packaging" / "windows" / "gaspar.spec",
    RAIZ / "packaging" / "linux" / "gaspar.spec",
)
ARQUIVO_VERIFICADOR = RAIZ / "packaging" / "verifica_pacote.py"
PACOTE_MENSAGERIA = "gaspar.messaging"


def carregar_verificador():
    espec = importlib.util.spec_from_file_location("verifica_pacote_gaspar", ARQUIVO_VERIFICADOR)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


MODULOS = carregar_verificador()


def nomes_de_gaspar_no_spec(caminho: Path) -> list[str]:
    """Toda string ``gaspar.*`` atribuida a ``hiddenimports``, na ordem do arquivo."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    vistos: list[str] = []
    for no in ast.walk(arvore):
        valor = no.value if isinstance(no, (ast.AugAssign, ast.Assign)) else None
        if not isinstance(valor, (ast.List, ast.Tuple)):
            continue
        for item in valor.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                if item.value == "gaspar" or item.value.startswith("gaspar."):
                    vistos.append(item.value)
    return vistos


def existe_no_codigo(nome: str) -> bool:
    try:
        return importlib.util.find_spec(nome) is not None
    except (ImportError, ValueError):
        return False


class PackagingManifestTestCase(unittest.TestCase):
    def setUp(self):
        self.esperados = set(MODULOS.modulos_no_codigo(PACOTE_MENSAGERIA))

    def test_a_varredura_do_codigo_enxerga_os_subpacotes(self):
        self.assertIn("gaspar.messaging", self.esperados)
        self.assertIn("gaspar.messaging.transports", self.esperados)
        self.assertIn("gaspar.messaging.transports.loopback", self.esperados)
        self.assertGreaterEqual(len(self.esperados), 13)

    def test_os_dois_specs_listam_a_mensageria_inteira(self):
        for spec in SPECS:
            with self.subTest(spec=spec.relative_to(RAIZ).as_posix()):
                listados = set(nomes_de_gaspar_no_spec(spec))
                faltando = sorted(self.esperados - listados)
                self.assertEqual([], faltando, f"faltam modulos no hiddenimports de {spec}")

    def test_os_dois_specs_tem_a_mesma_lista_de_modulos_gaspar(self):
        por_plataforma = {
            spec.parent.name: set(nomes_de_gaspar_no_spec(spec)) for spec in SPECS
        }
        self.assertEqual(
            {"windows", "linux"}, set(por_plataforma), "esperava os dois specs"
        )
        self.assertEqual(
            por_plataforma["windows"],
            por_plataforma["linux"],
            "os dois specs perderam sincronia",
        )

    def test_nenhum_nome_do_spec_aponta_para_codigo_que_nao_existe(self):
        for spec in SPECS:
            for nome in sorted(set(nomes_de_gaspar_no_spec(spec))):
                with self.subTest(nome=nome, spec=str(spec.parent.name)):
                    self.assertTrue(
                        existe_no_codigo(nome),
                        f"{nome} esta listado em {spec.name}, mas nao existe no codigo",
                    )

    def test_a_lista_nao_repete_o_mesmo_modulo(self):
        for spec in SPECS:
            vistos = nomes_de_gaspar_no_spec(spec)
            duplicados = sorted({nome for nome in vistos if vistos.count(nome) > 1})
            with self.subTest(spec=str(spec.parent.name)):
                self.assertEqual([], duplicados)

    def test_a_guarda_morde_com_um_modulo_a_menos(self):
        """Sem esta prova, o teste acima passaria mesmo com o parser quebrado."""
        esperados = sorted(self.esperados)
        casa = tempfile.TemporaryDirectory()
        self.addCleanup(casa.cleanup)
        spec_falso = Path(casa.name) / "gaspar.spec"
        linhas = "\n".join(f'    "{nome}",' for nome in esperados[:-1])
        spec_falso.write_text(f"hiddenimports = [\n{linhas}\n]\n", encoding="utf-8")
        listados = set(nomes_de_gaspar_no_spec(spec_falso))
        self.assertEqual(len(esperados) - 1, len(listados))
        self.assertEqual([esperados[-1]], sorted(self.esperados - listados))


if __name__ == "__main__":
    unittest.main()
