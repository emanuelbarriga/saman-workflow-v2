"""Tests del helper puro del Path Manager (cambio path-manager-panel, slice P1).

Cubre el helper ``SamanTools/ui/path_manager.py`` (TDD estricto, Qt-free):

* REQ-1 — pureza y determinismo: sin nuke/PySide en el modulo, sin lectura ni
  mutacion de ``os.environ``; inputs identicos → salidas identicas.
* REQ-2 — lectura de perfil activo: par conocido → 3 roots ficticias por
  plataforma; par desconocido → marcador de onboarding SIN escribir el store
  y sin raise; ``detectar_desconocido`` replica la escalera D2 en solo-lectura
  (par exacto → user-only default → hostname ajeno → miss).
* REQ-3 — estado de unidad: ``entorno.estado_unidad`` consultado sobre la
  base del SO actual (perfil conocido) o sobre la primera candidata de
  ``entorno.rutas_base`` (sin perfil); conectado/desconectado via monkeypatch.
* REQ-4 — cambio de base (D7): READ-MERGE-WRITE via ``guardar_perfiles``;
  cambia SOLO la entrada matched (exact/foreign-host → ``hosts[hostname]``;
  user-default → ``default`` + ``hosts[hostname]``); otras raices y otros
  usuarios intactos; env delta con ``PROJECT_ROOT``; ``os.environ`` intacto.
* REQ-5 — onboarding (D3): ``asegurar_perfil`` con slotting de la base
  inyectada; el store gana el par con roots ficticias; env delta con la raiz
  del SO actual; ``os.environ`` intacto.

Todas las rutas son ficticias (``/Volumes/estudio/2026``, ``L:/VFX/2026``,
``/mnt/estudio/2026``); ninguna ruta real del estudio aparece en fixtures.
"""

import json
import os

import pytest

from SamanTools.core import entorno
from SamanTools.ui import path_manager
from test_no_import_nuke_en_core import detectar_violaciones

_ROOTS = {
    "macOS": "/Volumes/estudio/2026",
    "Windows": "L:/VFX/2026",
    "Linux": "/mnt/estudio/2026",
}


def _escribir_store(tmp_path, perfiles):
    """Escribe un store ficticio y devuelve su ruta como string."""
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text(
        json.dumps({"perfiles": perfiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(ruta)


def _snapshot_env():
    return dict(os.environ)


def _marcar_conectado(base):
    return {"conectado": True, "ruta": base, "detalle": "Conectado."}


# --- REQ-1: pureza, determinismo, Qt-free ------------------------------------


def test_helper_puro_sin_imports_prohibidos():
    with open(path_manager.__file__, "r", encoding="utf-8") as fh:
        texto = fh.read()
    assert detectar_violaciones(texto) == []


def test_helper_import_no_inyecta_nuke_ni_pyside():
    import importlib
    import sys

    sys.modules.pop("SamanTools.ui.path_manager", None)
    antes = set(sys.modules)
    importlib.import_module("SamanTools.ui.path_manager")
    nuevos = set(sys.modules) - antes
    prohibidos = [
        n for n in nuevos if n.split(".", 1)[0] in ("nuke", "PySide2", "PySide6")
    ]
    assert prohibidos == []


def test_estado_panel_mismos_inputs_mismos_outputs(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    r1 = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    r2 = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    assert r1 == r2
    assert _snapshot_env() == env_antes
    assert rutas_engine.leer_perfiles(ruta) == {"ana": {"hosts": {"ws1": _ROOTS}}}


def test_estado_panel_no_muta_os_environ_desconocido(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    monkeypatch.setattr(entorno, "estado_unidad", lambda b: {"conectado": False, "ruta": None, "detalle": "off"})
    env_antes = _snapshot_env()
    path_manager.estado_panel(ruta, "nuevo", "pc9", "macOS")
    assert _snapshot_env() == env_antes


# --- REQ-2: perfil activo + marcador de onboarding (sin escribir) ------------


def test_estado_panel_par_conocido_devuelve_roots(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}, "default": _ROOTS}})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    assert res["conocido"] is True
    assert res["perfil"] == _ROOTS
    assert res["base_actual"] == "/Volumes/estudio/2026"


def test_estado_panel_desconocido_marcador_sin_escribir(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    monkeypatch.setattr(entorno, "estado_unidad", lambda b: {"conectado": False, "ruta": None, "detalle": "off"})
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    res = path_manager.estado_panel(ruta, "nuevo", "pc9", "macOS")
    assert res["conocido"] is False
    assert res["perfil"] is None
    assert res["base_actual"] is None
    assert archivo.read_bytes() == antes


def test_detectar_desconocido_par_exacto_falso(tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    assert path_manager.detectar_desconocido(ruta, "ana", "ws1") is False


def test_detectar_desconocido_fallback_default_falso(tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": {"default": _ROOTS}})
    assert path_manager.detectar_desconocido(ruta, "ana", "pc99") is False


def test_detectar_desconocido_hostname_ajeno_falso(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws9": _ROOTS}}})
    assert path_manager.detectar_desconocido(ruta, "nadie", "ws9") is False


def test_detectar_desconocido_miss_verdadero_sin_escribir(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    assert path_manager.detectar_desconocido(ruta, "nuevo", "pc9") is True
    assert archivo.read_bytes() == antes


def test_detectar_desconocido_store_corrupto_no_raise(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert path_manager.detectar_desconocido(str(ruta), "ana", "ws1") is True


def test_paridad_emparejar_con_fuente_vs_resolver_sin_escribir(tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(
        tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}, "default": _ROOTS}}
    )
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    roots, fuente, dueno = path_manager._emparejar_con_fuente(
        "ana", "ws1", rutas_engine.leer_perfiles(ruta)
    )
    assert roots == rutas_engine.resolver_perfil("ana", "ws1", ruta)
    assert fuente == path_manager._FUENTE_EXACTA
    assert dueno == "ana"
    assert archivo.read_bytes() == antes  # la deteccion nunca escribe (D2)


# --- REQ-3: estado de unidad sobre la base del SO actual ---------------------


def test_estado_panel_unidad_conectada(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    registros = []

    def fake(base):
        registros.append(base)
        return _marcar_conectado(base)

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    res = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    assert res["unidad"] == {
        "conectado": True,
        "ruta": "/Volumes/estudio/2026",
        "detalle": "Conectado.",
    }
    assert registros == ["/Volumes/estudio/2026"]


def test_estado_panel_unidad_desconectada(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    monkeypatch.setattr(
        entorno,
        "estado_unidad",
        lambda b: {"conectado": False, "ruta": None, "detalle": "Mount colgado (timeout 3s)."},
    )
    res = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    assert res["unidad"]["conectado"] is False
    assert res["unidad"]["ruta"] is None
    assert res["unidad"]["detalle"]


def test_estado_panel_desconocido_consulta_primera_candidata(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    registros = []

    def fake(base):
        registros.append(base)
        return {"conectado": False, "ruta": None, "detalle": "off"}

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    res = path_manager.estado_panel(ruta, "nuevo", "pc9", "macOS")
    assert res["conocido"] is False
    assert registros == [entorno.rutas_base("macOS")[0]]


# --- REQ-4: cambio de base (READ-MERGE-WRITE, D7) ----------------------------


def test_cambio_base_mac_2027_conserva_resto_y_otros_usuarios(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(
        tmp_path,
        {
            "ana": {"hosts": {"ws1": _ROOTS}, "default": _ROOTS},
            "pedro": {"hosts": {"ws2": _ROOTS}},
        },
    )
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    res = path_manager.preparar_cambio_base(
        "ana", "ws1", ruta, "macOS", "/Volumes/estudio/2027"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["hosts"]["ws1"]["macOS"] == "/Volumes/estudio/2027"
    assert store["ana"]["hosts"]["ws1"]["Windows"] == "L:/VFX/2026"
    assert store["ana"]["hosts"]["ws1"]["Linux"] == "/mnt/estudio/2026"
    assert store["ana"]["default"] == _ROOTS  # fuente exacta: default intacto
    assert store["pedro"] == {"hosts": {"ws2": _ROOTS}}
    assert res["perfil"]["macOS"] == "/Volumes/estudio/2027"
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert _snapshot_env() == env_antes


def test_cambio_base_fuente_default_actualiza_default_y_host(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": {"default": _ROOTS}})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    path_manager.preparar_cambio_base("ana", "ws5", ruta, "macOS", "/Volumes/estudio/2027")
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["hosts"]["ws5"]["macOS"] == "/Volumes/estudio/2027"
    assert store["ana"]["hosts"]["ws5"]["Windows"] == "L:/VFX/2026"
    assert store["ana"]["default"]["macOS"] == "/Volumes/estudio/2027"
    assert store["ana"]["default"]["Windows"] == "L:/VFX/2026"


def test_cambio_base_host_ajeno_actualiza_solo_ese_host(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(
        tmp_path,
        {"pedro": {"hosts": {"ws9": _ROOTS, "ws2": _ROOTS}, "default": _ROOTS}},
    )
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_cambio_base(
        "nadie", "ws9", ruta, "macOS", "/Volumes/estudio/2027"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["pedro"]["hosts"]["ws9"]["macOS"] == "/Volumes/estudio/2027"
    assert store["pedro"]["hosts"]["ws9"]["Windows"] == "L:/VFX/2026"
    assert store["pedro"]["hosts"]["ws2"] == _ROOTS
    assert store["pedro"]["default"] == _ROOTS
    assert res["perfil"]["macOS"] == "/Volumes/estudio/2027"


def test_cambio_base_desconocido_lanza_error_claro(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    with pytest.raises(ValueError):
        path_manager.preparar_cambio_base(
            "nuevo", "pc9", ruta, "macOS", "/Volumes/estudio/2027"
        )


# --- REQ-5: onboarding (asegurar_perfil, slotting) ---------------------------


def test_onboarding_persiste_par_con_roots_ficticias(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    res = path_manager.preparar_onboarding(
        "nuevo", "pc9", ruta, "/Volumes/estudio/2026", "macOS"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["hosts"]["pc9"] == _ROOTS
    assert store["nuevo"]["default"] == _ROOTS
    assert store["pedro"]["hosts"]["ws2"] == _ROOTS
    assert res["perfil"] == _ROOTS
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert _snapshot_env() == env_antes


def test_onboarding_slotting_linux(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_onboarding(
        "nuevo", "pc9", ruta, "/mnt/estudio/2027", "Linux"
    )
    esperadas = {
        "macOS": "/Volumes/estudio/2026",
        "Windows": "L:/VFX/2026",
        "Linux": "/mnt/estudio/2027",
    }
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["hosts"]["pc9"] == esperadas
    assert res["perfil"] == esperadas
    assert res["env"]["PROJECT_ROOT"] == "/mnt/estudio/2027"