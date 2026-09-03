"""Guardia de pureza de ``SamanTools/core`` y de higiene de tokens reales.

Este archivo es el test de guardia del cambio core-rutas-engine (slice G1):

* ``detectar_violaciones(texto)`` — matcher unico (estatico + dinamico) que
  detecta imports de modulos prohibidos (nuke, nukescripts, PySide2, PySide6).
* ``auditar_tokens(raiz)`` — escaneo de higiene: tokens reales del estudio
  (wupm, LucidLink, HTLR, PCF) prohibidos en codigo de un repositorio publico.

El propio archivo es self-exempt del escaneo de tokens: debe nombrarlos para
definir las expresiones regulares. Los tests usan muestras sinteticas para
probar el matcher sin contaminar modulos reales.
"""

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_DIR_CORE = _RAIZ / "SamanTools" / "core"

_MODULOS_PROHIBIDOS = ("nuke", "nukescripts", "PySide2", "PySide6")
_ALTERNANCIA = "|".join(_MODULOS_PROHIBIDOS)

_PATRON_IMPORT = re.compile(
    r"^\s*(?:import\s+(?:" + _ALTERNANCIA + r")\b"
    r"|from\s+(?:" + _ALTERNANCIA + r")\b)"
    r"|(?:__import__|import_module)\s*\(\s*['\"](?:" + _ALTERNANCIA + r")['\"]"
)

_PATRON_TOKENS_REALES = re.compile(r"wupm|LucidLink|HTLR|PCF", re.IGNORECASE)


def detectar_violaciones(texto: str) -> list[str]:
    """Devuelve las lineas de ``texto`` que importan modulos prohibidos.

    Un solo matcher cubre ambos casos (D7): importaciones estaticas ancladas
    al inicio de linea (patron anclado a import/from) y llamadas dinamicas
    sin anclar (``__import__`` / ``import_module`` con el modulo entre
    comillas). Comentarios y literales de string que solo MENCIONAN el
    nombre pasan.
    """
    return [linea for linea in texto.splitlines() if _PATRON_IMPORT.search(linea)]


def auditar_tokens(raiz: Path) -> list[str]:
    """Devuelve las violaciones de tokens reales del estudio bajo ``raiz``.

    Escaneo recursivo de ``*.py`` (salta ``__pycache__``) con coincidencia
    case-insensitive de los tokens prohibidos. El propio archivo de guardia es
    self-exempt: debe nombrar los tokens para definir las expresiones.
    """
    violaciones: list[str] = []
    archivo_guardia = Path(__file__).resolve()
    for py in sorted(raiz.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        if py.resolve() == archivo_guardia:
            continue
        contenido = py.read_text(encoding="utf-8", errors="replace")
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            if _PATRON_TOKENS_REALES.search(linea):
                violaciones.append(f"{py}:{numero}: token real del estudio")
    return violaciones


# --- Matcher: muestras sinteticas -----------------------------------------


def test_detectar_import_nuke_estatico():
    texto = "import nuke\nprint('hola')\n"
    assert detectar_violaciones(texto) == ["import nuke"]


def test_detectar_from_pyside6():
    texto = "from PySide6.QtWidgets import QWidget\n"
    assert detectar_violaciones(texto) == ["from PySide6.QtWidgets import QWidget"]


def test_detectar_from_pyside2():
    texto = "from PySide2 import QtWidgets\n"
    assert detectar_violaciones(texto) == ["from PySide2 import QtWidgets"]


def test_detectar_import_nukescripts():
    texto = "import nukescripts\n"
    assert detectar_violaciones(texto) == ["import nukescripts"]


def test_detectar_importlib_import_module_nuke():
    texto = 'def cargar():\n    return importlib.import_module("nuke")\n'
    assert detectar_violaciones(texto) == ['    return importlib.import_module("nuke")']


def test_detectar_dunder_import_nuke():
    texto = "mod = __import__('nuke')\n"
    assert detectar_violaciones(texto) == ["mod = __import__('nuke')"]


def test_detectar_dunder_import_nukescripts():
    texto = 'mod = __import__("nukescripts")\n'
    assert detectar_violaciones(texto) == ['mod = __import__("nukescripts")']


def test_detectar_import_module_pyside6_comilla_simple():
    texto = "mod = importlib.import_module('PySide6')\n"
    assert detectar_violaciones(texto) == ["mod = importlib.import_module('PySide6')"]


def test_detectar_import_module_os_pasa():
    texto = "import os\nimportlib.import_module('os')\n"
    assert detectar_violaciones(texto) == []


def test_detectar_comentario_import_nuke_pasa():
    texto = "# import nuke dentro del caller\n"
    assert detectar_violaciones(texto) == []


def test_detectar_import_nuke_extra_no_matchea():
    texto = "import nuke_extra  # modulo ajeno\n"
    assert detectar_violaciones(texto) == []


def test_detectar_literal_string_import_nuke_pasa():
    texto = 'x = "import nuke"\n'
    assert detectar_violaciones(texto) == []


# --- Guardia real sobre el arbol -------------------------------------------------


def test_guard_core_real_limpio():
    violaciones_por_archivo = {}
    for py in sorted(_DIR_CORE.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        halladas = detectar_violaciones(py.read_text(encoding="utf-8", errors="replace"))
        if halladas:
            violaciones_por_archivo[str(py.relative_to(_RAIZ))] = halladas
    assert violaciones_por_archivo == {}


def test_guard_arbol_real_sin_tokens():
    violaciones = auditar_tokens(_RAIZ / "SamanTools") + auditar_tokens(_RAIZ / "tests")
    assert violaciones == []


# --- Higiene de tokens: muestras sinteticas --------------------------------------


def test_auditar_tokens_marca_token_real(tmp_path):
    fuente = tmp_path / "modulo.py"
    fuente.write_text('BASE = "/Volumes/wupm/2026"\n', encoding="utf-8")
    halladas = auditar_tokens(tmp_path)
    assert len(halladas) == 1
    assert "modulo.py:1" in halladas[0]


def test_auditar_tokens_es_case_insensitive(tmp_path):
    fuente = tmp_path / "modulo.py"
    fuente.write_text('BASE = "/Volumes/WUPM/2026"\n', encoding="utf-8")
    assert len(auditar_tokens(tmp_path)) == 1


def test_auditar_tokens_fuentes_neutralizadas_pasan(tmp_path):
    fuente = tmp_path / "modulo.py"
    fuente.write_text('BASE = "/Volumes/estudio/2026"\nCINE = "CINE"\n', encoding="utf-8")
    assert auditar_tokens(tmp_path) == []


def test_auditar_tokens_ignora_pycache(tmp_path):
    con_token = tmp_path / "__pycache__" / "modulo.py"
    con_token.parent.mkdir()
    con_token.write_text('BASE = "/Volumes/wupm/2026"\n', encoding="utf-8")
    assert auditar_tokens(tmp_path) == []