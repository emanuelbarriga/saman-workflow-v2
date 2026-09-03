"""
Tests de SamanTools.ui.injector — slices H1 (load-contract) + S2
(perfil-por-usuario: cadena de store proyecto-primero + probe anti-hang).

El injector es la capa de carga que ensambla el entorno como DATOS puros
(``armar_estado_env``) y lo aplica a ``os.environ`` + ``__main__`` en una
capa fina separada (``aplicar_entorno``). NO importa nuke: se testean con
pytest directo, sin stub, igual que el nucleo.

Este archivo cubre:

* Ensamblado puro (S1+S2 al spec): PROJECT_ROOT por CORTE ESTRUCTURAL del
  plato; la base inyectada es SOLO fallback (nunca pisa un corte valido);
  sin corte ni base cae a la root del perfil para el SO explicito (AD7).
  PYTHON_* SIEMPRE = raices del perfil 3x3 para el SO explicito (espacio
  faltante → fallback hermano reconstruir_rutas del motor, AD7).
* Espacios extra (espacios-extra, PR 5): ``armar_estado_env`` emite
  ``PYTHON_<extra>`` SORTED despues del trio canonico (D3); un extra sin
  root para el SO explicito se OMITE — nunca aparece como clave vacia.
* Cadena de store proyecto-primero (AD5): ``obtener_ruta_store(raiz)`` —
  ``{raiz}/.saman/nuke_profiles.json`` gana SIEMPRE que exista, luego
  ``NUKE_PROFILES_PATH`` -> ``SamanTools.config_local`` (scoped) -> home.
* Probe anti-hang (R2/D6): ``_probe_store`` = ``estado_unidad(dirname)``
  (subprocess + timeout + cache ~10s del motor) y recien ahi ``os.path.isfile``
  — un mount muerto cortocircuita sin colgar y JAMAS crea ``.saman/`` en
  lectura (nace lazy en la primera escritura, bajo lock del motor).
* Aplicacion idempotente, helper de override ``project_directory`` y la
  maquinaria de precedencia + cache en memoria (ADR-2/ADR-3).

Todas las rutas son ficticias (/Volumes/estudio/2026, L:/VFX/2026) o de dev.
"""

import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

from SamanTools.core import entorno
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
    # Spec S2: la base cubre SOLO el PROJECT_ROOT; las PYTHON_* son las raices
    # del perfil para el SO explicito (ningun espacio del perfil se pierde).
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"


def test_ruta_fuera_de_toda_root_inyecta_base():
    """Camino distinto del gap: la ruta existe pero no cae bajo ninguna root."""
    contexto_crudo = rutas_engine.get_context(PERFIL_TRIPLE, "/tmp/fuera.nk")
    assert contexto_crudo["project_root"] is None
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "macOS", "/tmp/fuera.nk", base="/Volumes/estudio/2026"
    )
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    # PYTHON_* del perfil para el SO explicito (spec S2), no del hermano base.
    assert env["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"


def test_base_no_pisa_un_corte_valido():
    """Spec S2: la base es FALLBACK — un corte estructural presente gana."""
    env = injector.armar_estado_env(
        PERFIL_TRIPLE, "macOS", RUTA_COMP, base="/Volumes/estudio/2026/OTRO_COMP"
    )
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert env["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"


def test_sin_corte_sin_base_raiz_espacio_so():
    """AD7: untitled sin base -> la root del perfil para el SO explicito."""
    env = injector.armar_estado_env(PERFIL_TRIPLE, "macOS", "")
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"


def test_sin_corte_sin_base_primer_espacio_con_so():
    """Triangulacion: sin TO_VFX para el SO, el fallback va al siguiente espacio."""
    perfil = {
        "TO_VFX": {"Windows": "L:/VFX/2026/CINE/TO_VFX"},
        "COMP": {"macOS": "/Volumes/estudio/2026/CINE/COMP"},
    }
    env = injector.armar_estado_env(perfil, "macOS", "")
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE/COMP"


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


# --- Espacios extra via armar_estado_env (espacios-extra, PR 5) ---------------


PERFIL_CON_EXTRAS = dict(PERFIL_TRIPLE)
PERFIL_CON_EXTRAS["3D"] = {"macOS": "/Volumes/estudio/2026/CINE/3D"}
PERFIL_CON_EXTRAS["PREVIEW"] = {"macOS": "/Volumes/estudio/2026/CINE/PREVIEW"}


def test_armar_estado_env_extras_sorted_tras_canonico():
    """Spec D3: extras emiten PYTHON_* SORTED despues del trio canonico."""
    env = injector.armar_estado_env(PERFIL_CON_EXTRAS, "macOS", RUTA_COMP)
    claves = list(env)
    # Trio canonico primero (orden _ESPACIOS), luego los extras SORTED.
    assert claves.index("PYTHON_TO_VFX") < claves.index("PYTHON_3D")
    assert claves.index("PYTHON_COMP") < claves.index("PYTHON_3D")
    assert claves.index("PYTHON_FROM_VFX") < claves.index("PYTHON_3D")
    assert claves.index("PYTHON_3D") < claves.index("PYTHON_PREVIEW")
    assert env["PYTHON_3D"] == "/Volumes/estudio/2026/CINE/3D"
    assert env["PYTHON_PREVIEW"] == "/Volumes/estudio/2026/CINE/PREVIEW"


def test_armar_estado_env_extra_sin_root_para_so_se_omite():
    """Spec D4: extra sin root para el SO explicito se OMITE, nunca ''."""
    # "3D" y "PREVIEW" solo tienen root macOS; para Windows no hay slot.
    env = injector.armar_estado_env(PERFIL_CON_EXTRAS, "Windows", "")
    assert "PYTHON_3D" not in env
    assert "PYTHON_PREVIEW" not in env
    # El trio canonico sigue presente con las raices de Windows.
    assert env["PYTHON_TO_VFX"] == "L:/VFX/2026/CINE/TO_VFX"
    assert env["PYTHON_COMP"] == "L:/VFX/2026/CINE/COMP"
    # Nunca una clave con valor vacio (contrato AD7/D4).
    assert "" not in env.values()


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


# --- S2: cadena proyecto-primero (AD5) + probe anti-hang (R2/D6) --------------

_ESTADO_CONECTADO = {
    "conectado": True,
    "ruta": None,
    "detalle": "Conectado.",
}
_ESTADO_DESCONECTADO = {
    "conectado": False,
    "ruta": None,
    "detalle": "Mount colgado (timeout 3s).",
}


def test_store_proyecto_gana_siempre(tmp_path, monkeypatch, sin_config_local_real):
    """AD5: con ``.saman/nuke_profiles.json`` presente, el store del proyecto
    gana hasta al env var (la cadena es proyecto-primero)."""
    raiz = tmp_path / "CINE"
    store = raiz / ".saman" / "nuke_profiles.json"
    store.parent.mkdir(parents=True)
    store.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NUKE_PROFILES_PATH", "/ficticio/env/nuke_profiles.json")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        entorno, "estado_unidad", lambda r: dict(_ESTADO_CONECTADO, ruta=r)
    )
    assert injector.obtener_ruta_store(str(raiz)) == str(store)


def test_store_proyecto_sin_archivo_gana_si_dirname_responde(tmp_path, monkeypatch, sin_config_local_real):
    """UX fix: si el dirname ``{raiz}/.saman`` responde aunque no exista el
    .json, el store del proyecto GANA (el onboarding lo crea AHÍ, no en home)."""
    (tmp_path / "CINE" / ".saman").mkdir(parents=True)
    monkeypatch.setenv("NUKE_PROFILES_PATH", "/ficticio/env/nuke_profiles.json")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        entorno, "estado_unidad", lambda r: dict(_ESTADO_CONECTADO, ruta=r)
    )
    assert (
        injector.obtener_ruta_store(str(tmp_path / "CINE"))
        == str(tmp_path / "CINE" / ".saman" / "nuke_profiles.json")
    )


def test_store_proyecto_dirname_no_responde_cae_al_env(tmp_path, monkeypatch, sin_config_local_real):
    """R2/D6: mount desconectado -> el probe de dirname falla SIN colgar;
    cae al env var incluso con el .json presente."""
    raiz = tmp_path / "CINE"
    store = raiz / ".saman" / "nuke_profiles.json"
    store.parent.mkdir(parents=True)
    store.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NUKE_PROFILES_PATH", "/ficticio/env/nuke_profiles.json")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(entorno, "estado_unidad", lambda r: dict(_ESTADO_DESCONECTADO))
    assert injector.obtener_ruta_store(str(raiz)) == "/ficticio/env/nuke_profiles.json"


def test_store_proyecto_sin_saman_cae_a_home(tmp_path, monkeypatch, sin_config_local_real):
    """Sin ``.saman``, sin env ni config_local, la cadena termina en home."""
    raiz = tmp_path / "CINE"
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(entorno, "estado_unidad", lambda r: dict(_ESTADO_DESCONECTADO))
    esperado = str(tmp_path / "home" / ".config" / "saman" / "nuke_profiles.json")
    assert injector.obtener_ruta_store(str(raiz)) == esperado


def test_store_raiz_none_o_vacia_no_probea_y_usa_env(monkeypatch, sin_config_local_real, tmp_path):
    """Sin raiz de proyecto (untitled/fuera de root) la cadena arranca en el env."""
    monkeypatch.setenv("NUKE_PROFILES_PATH", "/ficticio/env/nuke_profiles.json")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert injector.obtener_ruta_store(None) == "/ficticio/env/nuke_profiles.json"
    assert injector.obtener_ruta_store("   ") == "/ficticio/env/nuke_profiles.json"


def test_probe_mount_muerto_cortocircuita_sin_isfile(monkeypatch):
    """R2/D6: dirname desconectado -> el probe NO ejecuta ``os.path.isfile``
    (un stat sobre un mount muerto colgaria; el timeout lo absorbe
    ``estado_unidad`` y el cortocircuito evita el stat)."""
    llamadas = {"isfile": 0}
    real_isfile = os.path.isfile

    def espia_isfile(ruta):
        llamadas["isfile"] += 1
        return real_isfile(ruta)

    monkeypatch.setattr(entorno, "estado_unidad", lambda r: dict(_ESTADO_DESCONECTADO))
    monkeypatch.setattr(os.path, "isfile", espia_isfile)
    assert (
        injector._probe_store("/ficticio/proyecto/.saman/nuke_profiles.json") is False
    )
    assert llamadas["isfile"] == 0


def test_probe_valida_dirname_y_archivo(monkeypatch, tmp_path):
    """D6: el probe consulta el DIRNAME via estado_unidad y luego el archivo."""
    padre = tmp_path / "CINE" / ".saman"
    padre.mkdir(parents=True)
    ruta = padre / "nuke_profiles.json"
    ruta.write_text("{}", encoding="utf-8")
    vistos = []

    monkeypatch.setattr(
        entorno,
        "estado_unidad",
        lambda r: vistos.append(r) or dict(_ESTADO_CONECTADO, ruta=r),
    )
    assert injector._probe_store(str(ruta)) is True
    assert vistos == [str(padre)]
    # Triangulacion: el dirname responde pero el archivo no existe -> False.
    assert injector._probe_store(str(padre / "ausente.json")) is False


def test_probe_reutiliza_cache_estado_unidad(monkeypatch, tmp_path):
    """D6: probes repetidos dentro de la cache ~10s no re-verifican el mount.

    La cache vive DENTRO de ``entorno.estado_unidad``: el spy se coloca en
    ``_verificar_ruta`` (el runner de subprocess) — el segundo probe absorbe
    el resultado cacheado y el subprocess corre una sola vez.
    """
    ruta = tmp_path / "CINE" / ".saman" / "nuke_profiles.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{}", encoding="utf-8")
    real_verificar = entorno._verificar_ruta
    llamadas = {"n": 0}

    def espia(base):
        llamadas["n"] += 1
        return real_verificar(base)

    monkeypatch.setattr(entorno, "_verificar_ruta", espia)
    assert injector._probe_store(str(ruta)) is True
    assert injector._probe_store(str(ruta)) is True
    assert llamadas["n"] == 1


def test_probe_no_crea_saman_en_lectura(tmp_path, monkeypatch, sin_config_local_real):
    """AD6: la cadena de LECTURA nunca crea ``.saman/`` (nace lazy en escritura)."""
    raiz = tmp_path / "CINE"
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(entorno, "estado_unidad", lambda r: dict(_ESTADO_DESCONECTADO))
    injector.obtener_ruta_store(str(raiz))
    assert not (raiz / ".saman").exists()
    assert not (raiz / ".saman" / "nuke_profiles.json").exists()


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
    # El override fuerza SOLO el PROJECT_ROOT; las PYTHON_* del perfil quedan
    # intactas (spec S2: raices del perfil para el SO explicito).
    assert final["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
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