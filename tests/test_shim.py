"""
Tests de SamanTools.rutas — slice H2 del cambio load-contract (shim V1).

El shim mantiene vivo el contrato de los comps V1
(``from SamanTools import rutas; rutas.actualizar(nuke.thisNode())``) sin
importar nuke a nivel de modulo y sin tocar ``SamanTools/core``.

Reglas del slice (spec load-shim + ADR-3/ADR-8):

  - Import headless: el modulo debe importar sin stub de nuke; los type hints
    de tipos Nuke son strings (``"nuke.Node"``) y NO se evaluan al importar.
  - Constantes re-exportadas IDENTICAS a V1 (``SUFIJOS``, ``KNOBS_RUTAS_BASE``,
    ``KNOBS_VERSION_ACTUAL``, ``_KNOBS_A_MIGRAR``): valores serializados en
    ``.nk`` que no pueden cambiar.
  - Facades: ``actualizar`` respeta ADR-3 (el env del injector cacheado gana,
    el farm env pre-existente gana, solo si nada de eso aplica se escribe el
    env derivado de los knobs y SIEMPRE via ``injector.aplicar_entorno``).
  - Stubs compat-only: 5 no-ops que no tocan nuke, marcados como nunca
    revividos en su docstring.

Los fakes de nodo viven SOLO en este archivo (NUNCA en conftest): conftest no
define ningun stub de nuke y debe seguir intacto.
"""

import os
import re
import sys
import types
from pathlib import Path

import pytest

from SamanTools.ui import injector
from SamanTools import rutas

# ---------------------------------------------------------------------------
# Fakes locales al test file (prohibido en conftest por spec load-shim)
# ---------------------------------------------------------------------------


class KnobFake:
    """Knob fake minimo: value()/setValue()/toScript() (duck typing Nuke)."""

    def __init__(self, valor):
        self._valor = valor

    def value(self):
        return self._valor

    def setValue(self, valor):
        self._valor = valor

    def toScript(self):
        return str(self._valor)


class NodoFake:
    """Nodo fake minimo: knobs() + __getitem__ (duck typing Nuke)."""

    def __init__(self, knobs=None):
        self._knobs = dict(knobs or {})

    def knobs(self):
        return set(self._knobs)

    def __getitem__(self, nombre):
        return self._knobs[nombre]


class _KnobReload:
    """Knob 'reload' fake con contador de execute()."""

    def __init__(self):
        self.ejecutado = 0

    def execute(self):
        self.ejecutado += 1


class _FileKnob:
    """Knob 'file' fake: toScript() devuelve el script; fromScript() re-evalua."""

    def __init__(self, script, resuelta=None):
        self._script = script
        self._resuelta = resuelta if resuelta is not None else script

    def value(self):
        return self._resuelta

    def toScript(self):
        return self._script

    def fromScript(self, script):
        self._script = script
        self._resuelta = self._resuelta + "/re-resuelta"


class _NodoRead:
    """Nodo Read fake minimo: clase 'Read' + knobs 'file' y 'reload'."""

    class_ = "Read"

    def __init__(self, file_knob, reload_knob):
        self._file = file_knob
        self._reload = reload_knob

    def knobs(self):
        return {"file", "reload"}

    def __getitem__(self, nombre):
        return self._file if nombre == "file" else self._reload


class _NukeFake:
    """Nuke fake de modulo (sys.modules, local al test): allNodes()/thisNode/root."""

    def __init__(self, nodos=None):
        self._nodos = nodos or []

    def allNodes(self, clase=None):
        if clase is not None:
            return [n for n in self._nodos if getattr(n, "class_", None) == clase]
        return list(self._nodos)

    def thisNode(self):
        return None

    def root(self):
        raise AttributeError("sin root en headless")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

V1_KNOBS_RUTAS_BASE = (
    "TO_VFX_SERVER_MAC", "comp_SERVER_MAC", "FROM_VFX_SERVER_MAC",
    "TO_VFX_SERVER_WINDOWS", "comp_SERVER_WINDOWS", "FROM_VFX_SERVER_WINDOWS",
    "TO_VFX_SERVER_ARTIST", "comp_SERVER_ARTIST", "FROM_VFX_SERVER_ARTIST",
)

V1_SUFIJOS = {"MacServer": "MAC", "Windows": "WINDOWS", "Artist": "ARTIST"}

V1_KNOBS_VERSION_ACTUAL = frozenset(
    {
        "SeccionEntorno",
        "SO_Detectado",
        "EstadoUnidad",
        "UsuarioRecomendado",
        "ProyectoDetectado",
        "CapituloDetectado",
        "PlanoDetectado",
    }
)

V1_KNOBS_A_MIGRAR = (
    "string",
    "UsuarioActivo",
    "TO_VFX_SERVER_MAC",
    "comp_SERVER_MAC",
    "FROM_VFX_SERVER_MAC",
    "TO_VFX_SERVER_WINDOWS",
    "comp_SERVER_WINDOWS",
    "FROM_VFX_SERVER_WINDOWS",
    "TO_VFX_SERVER_ARTIST",
    "comp_SERVER_ARTIST",
    "FROM_VFX_SERVER_ARTIST",
)

RUTAS_MAC = {
    "TO_VFX_SERVER_MAC": "/Volumes/estudio/2026/CINE/TO_VFX/",
    "comp_SERVER_MAC": "/Volumes/estudio/2026/CINE/COMP/",
    "FROM_VFX_SERVER_MAC": "/Volumes/estudio/2026/CINE/FROM_VFX/",
}


def _nodo_rutas_fake(valores_rutas=None):
    """Nodo Rutas fake: UsuarioActivo=MacServer + las 9 rutas base."""
    knobs = {"UsuarioActivo": KnobFake("MacServer")}
    for nombre in V1_KNOBS_RUTAS_BASE:
        knobs[nombre] = KnobFake("")
    for nombre, valor in (valores_rutas or {}).items():
        knobs[nombre] = KnobFake(valor)
    return NodoFake(knobs)


@pytest.fixture(autouse=True)
def _entorno_limpio_shim():
    """Aisla os.environ, __main__ y el cache del injector entre tests."""
    import __main__

    env_antes = dict(os.environ)
    main_antes = {k: v for k, v in vars(__main__).items() if k.isupper()}
    inj_antes = (injector._env_cache, injector._env_inyectado)
    yield
    for clave in set(os.environ) - set(env_antes):
        del os.environ[clave]
    for clave, valor in env_antes.items():
        os.environ[clave] = valor
    for clave, valor in main_antes.items():
        setattr(__main__, clave, valor)
    for clave in set(vars(__main__)) - set(main_antes):
        if clave.isupper():
            delattr(__main__, clave)
    injector._env_cache, injector._env_inyectado = inj_antes


# ---------------------------------------------------------------------------
# H2.1: import headless sin stub + anotaciones string
# ---------------------------------------------------------------------------


def test_import_headless_sin_stub():
    """Importar el shim no resuelve nuke y no deja rastro en sys.modules."""
    assert callable(rutas.actualizar)
    assert "nuke" not in sys.modules


def test_anotaciones_nuke_en_string_no_evaluan():
    """Los type hints de tipos Nuke son strings: nunca se resuelven."""
    assert rutas.actualizar.__annotations__["n"] == "nuke.Node"
    assert rutas.refrescar_fuentes.__annotations__["n"] == "nuke.Node"


def test_docstring_modulo_marca_shim_v2():
    """El docstring del modulo identifica el shim V2 que delega en core."""
    doc = rutas.__doc__ or ""
    assert "SamanTools V2 compat shim" in doc
    assert "delegates to core" in doc


# ---------------------------------------------------------------------------
# H2.2: constantes re-exportadas identicas a V1
# ---------------------------------------------------------------------------


def test_knobs_rutas_base_identica_v1():
    assert rutas.KNOBS_RUTAS_BASE == V1_KNOBS_RUTAS_BASE


def test_sufijos_identico_v1():
    assert rutas.SUFIJOS == V1_SUFIJOS


def test_knobs_version_actual_identico_v1():
    assert rutas.KNOBS_VERSION_ACTUAL == V1_KNOBS_VERSION_ACTUAL


def test_knobs_a_migrar_identico_v1():
    assert rutas._KNOBS_A_MIGRAR == V1_KNOBS_A_MIGRAR


# ---------------------------------------------------------------------------
# H2.3: actualizar + guard ADR-3 + es_nodo_rutas + es_version_actual
# ---------------------------------------------------------------------------


def test_actualizar_devuelve_bool_sin_excepcion():
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    resultado = rutas.actualizar(nodo)
    assert resultado is True


def test_actualizar_escribe_env_por_injector():
    os.environ.pop("PROJECT_ROOT", None)
    os.environ.pop("PYTHON_TO_VFX", None)
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.actualizar(nodo) is True
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert os.environ["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX/"
    assert os.environ["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP/"


def test_actualizar_respeta_env_inyectado_del_injector():
    """ADR-3: si el injector ya escribio esta sesion, el shim NO escribe env."""
    injector._env_inyectado = True
    injector._env_cache = {"PROJECT_ROOT": "/Volumes/estudio/2026"}
    os.environ.pop("PROJECT_ROOT", None)
    os.environ.pop("PYTHON_TO_VFX", None)
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.actualizar(nodo) is True  # igual sincroniza knobs
    assert os.environ.get("PROJECT_ROOT") is None
    assert os.environ.get("PYTHON_TO_VFX") is None


def test_actualizar_respeta_farm_env_preexistente():
    """ADR-3 caso 1: PROJECT_ROOT pre-existente (render farm) gana, no se escribe."""
    os.environ["PROJECT_ROOT"] = "/mnt/estudio/2026/CINE"
    os.environ.pop("PYTHON_TO_VFX", None)
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.actualizar(nodo) is True
    assert os.environ["PROJECT_ROOT"] == "/mnt/estudio/2026/CINE"
    assert os.environ.get("PYTHON_TO_VFX") is None


def test_actualizar_sin_nodo_devuelve_false():
    """Sin nuke (headless) y sin nodo: thisNode falla → False."""
    assert rutas.actualizar() is False


def test_es_nodo_rutas_true_por_knobs_independiente_del_nombre():
    nodo = NodoFake(
        {"UsuarioActivo": KnobFake("MacServer"), "TO_VFX_SERVER_MAC": KnobFake("/x/")}
    )
    assert rutas.es_nodo_rutas(nodo) is True


def test_es_nodo_rutas_false_sin_usuario_activo():
    nodo = NodoFake({"TO_VFX_SERVER_MAC": KnobFake("/x/")})
    assert rutas.es_nodo_rutas(nodo) is False


def test_es_nodo_rutas_false_solo_usuario_activo():
    nodo = NodoFake({"UsuarioActivo": KnobFake("MacServer")})
    assert rutas.es_nodo_rutas(nodo) is False


def test_es_nodo_rutas_none_o_sin_knobs_false():
    assert rutas.es_nodo_rutas(None) is False
    assert rutas.es_nodo_rutas(NodoFake({})) is False


def test_es_version_actual_true_con_todos_los_knobs():
    knobs = {nombre: KnobFake("") for nombre in V1_KNOBS_VERSION_ACTUAL}
    assert rutas.es_version_actual(NodoFake(knobs)) is True


def test_es_version_actual_false_si_falta_un_knob():
    knobs = {nombre: KnobFake("") for nombre in V1_KNOBS_VERSION_ACTUAL}
    del knobs["EstadoUnidad"]
    assert rutas.es_version_actual(NodoFake(knobs)) is False


# ---------------------------------------------------------------------------
# H2.4: aplicar_proyecto, refrescar_fuentes, encontrar_nodos_rutas,
#       refrescar_estado, _texto_estado y _reescribir_proyecto_en_rutas
# ---------------------------------------------------------------------------


def test_aplicar_proyecto_devuelve_bool():
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.aplicar_proyecto(nodo) is True


def test_aplicar_proyecto_sin_nodo_devuelve_false():
    assert rutas.aplicar_proyecto() is False


def test_refrescar_fuentes_sin_nuke_devuelve_cero():
    """Headless: sin nodo o sin nuke la tolerancia devuelve 0, sin excepcion."""
    assert rutas.refrescar_fuentes() == 0
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.refrescar_fuentes(nodo, forzar=True) == 0


def test_refrescar_fuentes_con_nuke_fake_recarga_uno(monkeypatch):
    """Con nuke fake: forzar=True recarga los Reads dinamicos; cuenta real > 0."""
    file_knob = _FileKnob("[python /ficticio/leer.py]")
    reload_knob = _KnobReload()
    nodo_read = _NodoRead(file_knob, reload_knob)
    monkeypatch.setitem(sys.modules, "nuke", _NukeFake([nodo_read]))
    recargados = rutas.refrescar_fuentes(nodo_read, forzar=True)
    assert recargados == 1
    assert reload_knob.ejecutado == 1


def test_encontrar_nodos_rutas_filtra_con_nuke_fake(monkeypatch):
    nodo_rutas = NodoFake(
        {"UsuarioActivo": KnobFake("MacServer"), "TO_VFX_SERVER_MAC": KnobFake("/x/")}
    )
    nodo_otro = NodoFake({"grado": KnobFake("5")})
    monkeypatch.setitem(sys.modules, "nuke", _NukeFake([nodo_rutas, nodo_otro]))
    hallados = rutas.encontrar_nodos_rutas()
    assert hallados == [nodo_rutas]


def test_encontrar_nodos_rutas_sin_nuke_devuelve_vacio():
    assert rutas.encontrar_nodos_rutas() == []


def test_refrescar_estado_devuelve_bool_sin_nuke():
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    assert rutas.refrescar_estado(nodo) is True


def test_refrescar_estado_guard_antireentrada():
    nodo = _nodo_rutas_fake(RUTAS_MAC)
    rutas._refrescando = True
    try:
        assert rutas.refrescar_estado(nodo) is False
    finally:
        rutas._refrescando = False


def test_texto_estado_conectado_con_detalle():
    assert (
        rutas._texto_estado({"conectado": True, "detalle": "Conectado."})
        == "Conectado - Conectado."
    )


def test_texto_estado_desconectado_sin_detalle():
    assert rutas._texto_estado({"conectado": False, "detalle": ""}) == "Desconectado"


def test_reescribir_proyecto_en_rutas_cambia_segmento():
    nuevos, cambios = rutas._reescribir_proyecto_en_rutas(RUTAS_MAC, "OTRO")
    assert cambios == 3
    assert nuevos["TO_VFX_SERVER_MAC"] == "/Volumes/estudio/2026/OTRO/TO_VFX/"
    assert nuevos["comp_SERVER_MAC"] == "/Volumes/estudio/2026/OTRO/COMP/"
    assert nuevos["FROM_VFX_SERVER_MAC"] == "/Volumes/estudio/2026/OTRO/FROM_VFX/"


def test_reescribir_proyecto_en_rutas_sin_match_no_cambia():
    rutas_dict = {"TO_VFX_SERVER_MAC": "/Volumes/estudio/2026/CINE/"}
    nuevos, cambios = rutas._reescribir_proyecto_en_rutas(rutas_dict, "OTRO")
    assert cambios == 0
    assert nuevos == rutas_dict


# ---------------------------------------------------------------------------
# H2.5: stubs compat-only (no-op import-safe, docstring marcado)
# ---------------------------------------------------------------------------


def test_stubs_compat_only_noop_sin_nuke():
    """Los 5 stubs devuelven None sin tocar nuke ni lanzar."""
    assert "nuke" not in sys.modules
    assert rutas.crear_o_reutilizar() is None
    assert rutas.cambiar_proyecto() is None
    assert rutas.avisar_duplicados() is None
    assert rutas.refrescar_fuentes_boton() is None
    assert rutas.ruta_nk_por_defecto() is None


def test_stubs_docstring_marca_compat_only():
    for nombre in (
        "crear_o_reutilizar",
        "cambiar_proyecto",
        "avisar_duplicados",
        "refrescar_fuentes_boton",
        "ruta_nk_por_defecto",
    ):
        assert "COMPAT-ONLY" in (getattr(rutas, nombre).__doc__ or "")


# ---------------------------------------------------------------------------
# H2.6: anti-leak — el shim nunca importa nuke a nivel de modulo
# ---------------------------------------------------------------------------

_PATRON_NUKE_NIVEL_MODULO = re.compile(r"^import\s+nuke\b|^from\s+nuke\b", re.M)


def test_shim_sin_import_nuke_a_nivel_modulo():
    fuente = Path(rutas.__file__).read_text(encoding="utf-8")
    assert _PATRON_NUKE_NIVEL_MODULO.search(fuente) is None