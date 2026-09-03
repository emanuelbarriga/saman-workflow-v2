"""
Tests del slice H5 del cambio load-contract — sample config_local + docs de
coexistencia V1/V2 + gate final.

H5 NO introduce logica nueva en el runtime: el injector ya tolera la
ausencia/vacio de ``SamanTools.config_local`` (cubierto en test_injector.py,
H1.2) y la cadena de integridad del bootstrap ya tiene probes (test_bootstrap,
H3). Lo que H5 SI entrega son artefactos verificables:

  - ``docs/ARQUITECTURA-V2.md``: guia de coexistencia V1/V2 (marcador distinto,
    reemplazo con consentimiento, inmune al uninstaller V1, migracion, shim)
    y la plantilla scoped de override local (``NUKE_PROFILES_PATH``).
  - ``SamanTools/config_local.py`` (gitignored): sample de override; verificamos
    aqui que ``.gitignore`` lo cubre a CUALQUIER profundidad (nunca anclado a
    la raiz del repo) y que la plantilla documentada nunca lleva rutas reales.

IDIOMA de los artefactos: el doc es un artefacto tecnico (ingles); los
docstrings son ES (estilo del repo). Este archivo de test sigue el patron
marker-test de test_bootstrap.py / guard de test_injector.py.
"""

import fnmatch
import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_RUTA_DOC = _RAIZ / "docs" / "ARQUITECTURA-V2.md"

# Tokens reales del estudio construidos EN RUNTIME a partir de piezas: el
# guard de higiene (tests/test_no_import_nuke_en_core.py) escanea el arbol
# y solo se auto-exime a si mismo; por eso este archivo junta las piezas en
# tiempo de ejecucion, sin subcadenas contiguas de tokens prohibidos.
_TOKENS_PROHIBIDOS = ("wu" + "pm", "Lucid" + "Link", "HT" + "LR", "PC" + "F")
_PATRON_TOKEN_REAL = re.compile(
    "|".join(map(re.escape, _TOKENS_PROHIBIDOS)), re.IGNORECASE
)
_PATRON_MARCADOR_V1 = re.compile(r"bootstrap de artista", re.IGNORECASE)


def _patron_gitignore_aplica(patron, ruta_relativa):
    """Semantica basica de gitignore: patron SIN '/' matchea el basename en
    cualquier nivel del arbol; patron con '/' es relativo a la raiz."""
    if "/" not in patron.rstrip("/"):
        return fnmatch.fnmatchcase(Path(ruta_relativa).name, patron)
    return fnmatch.fnmatchcase(ruta_relativa, patron)


def test_gitignore_cubre_config_local_en_cualquier_nivel():
    """El patron config_local.py debe ser de nombre (no anclado): cubre
    SamanTools/config_local.py y cualquier otro nivel, jamas la raiz sola."""
    lineas = (_RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    patron = None
    for linea in lineas:
        limpia = linea.strip()
        if limpia == "config_local.py":
            patron = limpia
            break
    assert patron is not None, "falta el patron 'config_local.py' en .gitignore"
    assert "/" not in patron, "patron anclado a la raiz: no cubre SamanTools/"
    assert _patron_gitignore_aplica(patron, "SamanTools/config_local.py") is True
    assert _patron_gitignore_aplica(patron, "config_local.py") is True
    assert _patron_gitignore_aplica(patron, "config_local.json") is False


def test_doc_coexistencia_cubre_contratos_clave():
    """El doc de coexistencia explica: marcador V2 distinto, reemplazo con
    consentimiento, inmunidad al uninstaller V1, migracion y shim."""
    texto = _RUTA_DOC.read_text(encoding="utf-8")
    assert "SamanTools V2 bootstrap" in texto
    assert "consent" in texto.lower()
    assert "V1" in texto and "uninstaller" in texto.lower()
    assert "migrat" in texto.lower()
    assert "shim" in texto.lower()
    assert _PATRON_MARCADOR_V1.search(texto) is None
    assert _PATRON_TOKEN_REAL.search(texto) is None


def test_doc_plantilla_config_local_scoped():
    """La plantilla vive documentada como modulo scoped dentro del paquete,
    con la clave exacta que lee el injector (NUKE_PROFILES_PATH), placeholder
    vacio y el hermano JSON — nunca un modulo en la raiz del repo."""
    texto = _RUTA_DOC.read_text(encoding="utf-8")
    assert "SamanTools/config_local.py" in texto
    assert "NUKE_PROFILES_PATH" in texto
    assert "config_local.json" in texto
    assert "NUKE_PROFILES_PATH = \"\"" in texto
    assert "repository root" in texto.lower() or "repo root" in texto.lower()


def test_doc_migracion_menciona_checkout_y_directorio_nuke():
    """La migracion documenta el reemplazo del checkout ~/.nuke/SamanTools por
    el de V2 con consentimiento explicito."""
    texto = _RUTA_DOC.read_text(encoding="utf-8")
    assert "~/.nuke/SamanTools" in texto
    assert "checkout" in texto.lower()