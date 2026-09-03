"""
Tests de SamanTools.ui.injector — slice H1 del cambio load-contract
(contrato de env actualizado al esquema 3x3 de perfil-por-usuario, S1).

El injector es la capa de carga que ensambla el entorno como DATOS puros
(``armar_estado_env``) y lo aplica a ``os.environ`` + ``__main__`` en una
capa fina separada (``aplicar_entorno``). Las funciones puras de H1 NO
importan nuke: se testean con pytest directo, sin stub, igual que el nucleo.

Este archivo cubre: ensamblado puro con el nuevo contrato (PROJECT_ROOT por
corte estructural del plato; PYTHON_* = raices del perfil 3x3 para el SO, o
derivadas de la base inyectada via el hermano reconstruir_rutas, AD7), cadena
de resolucion de store, aplicacion idempotente, helper de override
``project_directory`` y la maquinaria de precedencia + cache en memoria
(sub-parte pura de ``registrar_callbacks``, que llega en H4 al estar ligada a
nuke.ui). Todas las rutas son ficticias (/Volumes/estudio/2026) o de dev.
"""

import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

from SamanTools.core import rutas_engine

# El modulo bajo prueba NO existe todavia en RED: este import lo garantiza.
from SamanTools.ui import injector

# --- Fixtures y fakes ----------------------------------------------------------

PERFIL_TRIPLE = {
    "TO_VFX": {
        "macOS": "/Volumes/estudio/2026/CINE/TO_VFX",
        "Windows": "L:/VFX/2026/CINE/TO_VFX",
        "Linux": "/mnt/estudio/2026/CINE/TO_VFX",
    },
    "COMP": {
        "macOS": "/Volumes/estudio/2026/CINE/COMP",
        "Windows": "L:/VFX/2026/CINE/COMP",
        "Linux": "/mnt/estudio/2026/CINE/COMP",
    },
    "FROM_VFX": {
        "macOS": "/Volumes/estudio/2026/CINE/FROM_VFX",
        "Windows": "L:/VFX/2026/CINE/FROM_VFX",
        "Linux": "/mnt/estudio/2026/CINE/FROM_VFX",
    },
}

RUTA_COMP = "/Volumes/estudio/2026/CINE/TO_VFX/ep.nk"


class _FakeKnob:
    """Knob fake: solo expone ``value()`` (duck typing estilo Nuke)."""

    def __init__(self, valor):
        self._valor = valor

    def value(self):
        return self._valor


class _FakeRoot:
    """Root fake: ``knobs()`` devuelve un dict nombre -> knob."""

    def __init__(self, knobs):
        self._knobs = knobs

    def knobs(self):
        return self._knobs


class _SinMetodoKnobs:
    """Root degenerado sin ``knobs()`` (defensa de ADR-5)."""


@pytest.fixture(autouse=True)
def _cache_env_limpio():
    """Aisla el cache de modulo entre tests de precedencia/cache."""
    injector._env_cache = None
    injector._env_inyectado = False
    yield
    injector._env_cache = None
    injector._env_inyectado = False


@pytest.fixture
def entorno_limpio():
    """Snapshot de os.environ + ``__main__`` para tests de aplicar_entorno."""
    import __main__

    env_antes = dict(os.environ)
    main_antes = {
        k: v for k, v in vars(__main__).items() if k.isupper()
    }
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


def _falso_config_local(valor_attr=None, con_json=None):
    """Fake de ``SamanTools.config_local`` registrado en ``sys.modules``.

    ``con_json``: dict a volcar como hermano ``config_local.json`` en el
    directorio del modulo fake (ejercita la rama JSON del loader real).
    """
    modulo = types.ModuleType("SamanTools.config_local")
    if valor_attr is not None:
        modulo.NUKE_PROFILES_PATH = valor_attr
    if con_json is not None:
        directorio = con_json["dir"]
        (directorio / "config_local.json").write_text(
            json.dumps(con_json["datos"]), encoding="utf-8"
        )
        modulo.__file__ = str(directorio / "config_local.py")
    else:
        modulo.__file__ = "/ficticio/SamanTools/config_local.py"
    return modulo


@pytest.fixture
def sin_config_local_real():
    """Quita cualquier config_local real del interpretre para aislamiento."""
    sys.modules.pop("SamanTools.config_local", None)
    yield
    sys.modules.pop("SamanTools.config_local", None)


# --- H1.1: armar_estado_env (pura, contrato 3x3) -------------------------------


def test_env_completo_bajo_root():
    """Corte estructural del plato -> PROJECT_ROOT; PYTHON_* del perfil 3x3."""
    env = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert env["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"
    assert env["PYTHON_FROM_VFX"] == "/Volumes/estudio/2026/CINE/FROM_VFX"


def test_untitled_gap_2286_inyecta_base():
    """Precondicion: el engine no corta un script sin ruta (project_root None)."""
    contexto_crudo = rutas_engine.get_context(PERFIL_TRIPLE, "")
    assert contexto_crudo["project_root"] is None
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "macOS", "", base="/Volumes/estudio/2026"
    )
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    # Con base inyectada las PYTHON_* se derivan del hermano de esa base (AD7).
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/COMP"


def test_ruta_fuera_de_toda_root_inyecta_base():
    """Camino distinto del gap: la ruta existe pero no cae bajo ninguna root."""
    contexto_crudo = rutas_engine.get_context(PERFIL_TRIPLE, "/tmp/fuera.nk")
    assert contexto_crudo["project_root"] is None
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "macOS", "/tmp/fuera.nk", base="/Volumes/estudio/2026"
    )
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert env["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/TO_VFX"


def test_determinista_entre_llamadas():
    env1 = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    env2 = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    assert env1 == env2
    assert env1 is not env2


def test_no_muta_os_environ_ni_main():
    import __main__

    env_antes = dict(os.environ)
    main_antes = dict(__main__.__dict__)
    injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    assert dict(os.environ) == env_antes
    assert dict(__main__.__dict__) == main_antes
    assert "PROJECT_ROOT" not in os.environ


def test_base_por_plataforma_windows():
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "Windows", "L:/VFX/2026/CINE/TO_VFX/ep.nk"
    )
    assert env["PROJECT_ROOT"] == "L:/VFX/2026/CINE"
    assert env["PYTHON_TO_VFX"] == "L:/VFX/2026/CINE/TO_VFX"
    assert env["PYTHON_FROM_VFX"] == "L:/VFX/2026/CINE/FROM_VFX"


def test_sin_base_posible_devuelve_env_vacio():
    # Perfil sin la plataforma pedida, sin base inyectada y ruta sin match.
    perfil_parcial = {"COMP": {"Windows": "L:/VFX/2026/CINE/COMP"}}
    assert injector.armar_estado_env(perfil_parcial, "macOS", "") == {}


# --- H1.2: obtener_ruta_store --------------------------------------------------


def test_env_var_gana(sin_config_local_real, monkeypatch):
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("NUKE_PROFILES_PATH", "/ficticio/proyecto/nuke_profiles.json")
    monkeypatch.setenv("HOME", "/ficticio/home")
    assert (
        injector.obtener_ruta_store()
        == "/ficticio/proyecto/nuke_profiles.json"
    )


def test_config_local_modulo_gana(sin_config_local_real, monkeypatch):
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", "/ficticio/home")
    falso = _falso_config_local(
        valor_attr="/ficticio/compartido/nuke_profiles.json"
    )
    monkeypatch.setitem(sys.modules, "SamanTools.config_local", falso)
    assert injector.obtener_ruta_store() == "/ficticio/compartido/nuke_profiles.json"


def test_config_local_json_hermano_gana(sin_config_local_real, monkeypatch, tmp_path):
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", "/ficticio/home")
    falso = _falso_config_local(
        con_json={
            "dir": tmp_path,
            "datos": {"NUKE_PROFILES_PATH": "/ficticio/json/nuke_profiles.json"},
        }
    )
    monkeypatch.setitem(sys.modules, "SamanTools.config_local", falso)
    assert injector.obtener_ruta_store() == "/ficticio/json/nuke_profiles.json"


def test_sin_env_ni_config_local_usa_home(sin_config_local_real, monkeypatch, tmp_path):
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    esperado = str(tmp_path / ".config" / "saman" / "nuke_profiles.json")
    assert injector.obtener_ruta_store() == esperado


def test_config_local_sin_valor_cae_a_home(
    sin_config_local_real, monkeypatch, tmp_path
):
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    falso = _falso_config_local(valor_attr="   ")
    monkeypatch.setitem(sys.modules, "SamanTools.config_local", falso)
    esperado = str(tmp_path / ".config" / "saman" / "nuke_profiles.json")
    assert injector.obtener_ruta_store() == esperado


# --- H1.3: aplicar_entorno (fina, idempotente) ---------------------------------


def test_escribe_os_environ_y_main(entorno_limpio):
    import __main__

    env = {"PROJECT_ROOT": "/Volumes/estudio/2026", "PYTHON_COMP": "/x/"}
    injector.aplicar_entorno(env)
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert __main__.PROJECT_ROOT == "/Volumes/estudio/2026"
    assert __main__.PYTHON_COMP == "/x/"


def test_idempotente_repite_sin_duplicar(entorno_limpio):
    import __main__

    env = {"PROJECT_ROOT": "/Volumes/estudio/2026"}
    injector.aplicar_entorno(env)
    injector.aplicar_entorno(env)
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert __main__.PROJECT_ROOT == "/Volumes/estudio/2026"


def test_env_vacio_no_escribe_nada(entorno_limpio):
    import __main__

    env_antes = dict(os.environ)
    main_antes = dict(__main__.__dict__)
    injector.aplicar_entorno({})
    assert dict(os.environ) == env_antes
    assert dict(__main__.__dict__) == main_antes


# --- H1.4: _override_proyecto_desde_root (puro, fake-root) ---------------------


def test_override_declarado_normaliza_a_forward():
    root = _FakeRoot(
        {"project_directory": _FakeKnob("/Volumes\\estudio\\2026\\OTRO_COMP")}
    )
    assert (
        injector._override_proyecto_desde_root(root)
        == "/Volumes/estudio/2026/OTRO_COMP"
    )


def test_override_declarado_con_slashes_ya_forward():
    root = _FakeRoot(
        {"project_directory": _FakeKnob("/Volumes/estudio/2026/OTRO_COMP")}
    )
    assert (
        injector._override_proyecto_desde_root(root)
        == "/Volumes/estudio/2026/OTRO_COMP"
    )


def test_override_vacio_o_blanco_no_declarado():
    root = _FakeRoot({"project_directory": _FakeKnob("   ")})
    assert injector._override_proyecto_desde_root(root) is None


def test_override_knob_faltante_no_declarado():
    root = _FakeRoot({"otro_knob": _FakeKnob("/Volumes/estudio/2026")})
    assert injector._override_proyecto_desde_root(root) is None


def test_override_root_sin_knobs_o_none():
    assert injector._override_proyecto_desde_root(_SinMetodoKnobs()) is None
    assert injector._override_proyecto_desde_root(None) is None


# --- H1.5 (sub-parte pura): precedencia + cache en memoria ---------------------


def test_precedencia_env_preexistente_gana():
    env = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    preexistente = {"PROJECT_ROOT": "/mnt/estudio/2026/CINE"}
    assert (
        injector._aplicar_precedencia(env, None, preexistente) is None
    )


def test_precedencia_override_gana():
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "macOS", RUTA_COMP, base="/Volumes/estudio/2026/OTRO_COMP"
    )
    env_antes = dict(os.environ)
    final = injector._aplicar_precedencia(
        env, "/Volumes/estudio/2026/OTRO_COMP", {}
    )
    assert final["PROJECT_ROOT"] == "/Volumes/estudio/2026/OTRO_COMP"
    # Las PYTHON_* derivadas de la base override (hermano de la raiz) se conservan.
    assert final["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/OTRO_COMP/TO_VFX"
    # El guard de precedencia es puro: no escribe nada en os.environ.
    assert dict(os.environ) == env_antes


def test_precedencia_perfil_default():
    env = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    final = injector._aplicar_precedencia(env, None, {})
    assert final == env
    assert final["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"


def test_cachear_env_guarda_y_marca_inyectado():
    env = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", RUTA_COMP)
    injector.cachear_env(env)
    assert injector._env_cache == env
    assert injector._env_inyectado is True


# --- Guardia: nuke nunca se importa a nivel de modulo en el injector -----------

_PATRON_IMPORT_NUKE = re.compile(r"^\s*(?:import\s+nuke\b|from\s+nuke\b)", re.M)


def test_injector_no_importa_nuke_a_nivel_modulo():
    fuente = Path(injector.__file__).read_text(encoding="utf-8")
    assert _PATRON_IMPORT_NUKE.search(fuente) is None