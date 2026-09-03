"""Tests del helper puro del Path Manager — contrato usuario-solo (S1).

Cubre el helper ``SamanTools/ui/path_manager.py`` (TDD estricto, Qt-free)
con el esquema 3x3 de perfil-por-usuario (AD1/AD2): el hostname y la
escalera (exact/default/host ajeno) DESAPARECEN; un perfil pertenece al
usuario con raices independientes por espacio y por SO.

* REQ-1 — pureza y determinismo: sin nuke/PySide en el modulo, sin lectura ni
  mutacion de ``os.environ``; inputs identicos → salidas identicas.
* REQ-2 — lectura de perfil activo: usuario con forma nueva → perfil 3x3 y
  raiz del SO actual (primera raiz no-None); desconocido O legacy → marcador
  de onboarding SIN escribir el store y sin raise; ``detectar_desconocido``
  replica la deteccion en solo-lectura (nunca ``resolver_perfil``).
* REQ-3 — estado de unidad: ``entorno.estado_unidad`` consultado sobre la
  raiz del SO actual (perfil conocido) o sobre la primera candidata de
  ``entorno.rutas_base`` (sin perfil).
* REQ-4 — cambio de base (D7): READ-MERGE-WRITE via ``guardar_perfiles``; la
  base nueva rellena el slot del SO en los TRES espacios; otras raices y
  otros usuarios intactos; env delta con ``PROJECT_ROOT``; sin perfil →
  ``ValueError``; ``os.environ`` intacto.
* REQ-5 — onboarding (D3): ``asegurar_perfil`` con slotting de la base
  inyectada; el store gana el perfil 3x3; env delta con la base;
  ``os.environ`` intacto.

Todas las rutas son ficticias (``/Volumes/estudio/2026/CINE/...``,
``L:/VFX/2026/CINE/...``, ``/mnt/estudio/2026/CINE/...``); ninguna ruta real
del estudio aparece en fixtures.
"""

import json
import os

import pytest

from SamanTools.core import entorno
from SamanTools.ui import path_manager
from test_no_import_nuke_en_core import detectar_violaciones

_ROOTS = {
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

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    r1 = path_manager.estado_panel(ruta, "ana", "macOS")
    r2 = path_manager.estado_panel(ruta, "ana", "macOS")
    assert r1 == r2
    assert _snapshot_env() == env_antes
    assert rutas_engine.leer_perfiles(ruta) == {"ana": _ROOTS}


def test_estado_panel_no_muta_os_environ_desconocido(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", lambda b: {"conectado": False, "ruta": None, "detalle": "off"})
    env_antes = _snapshot_env()
    path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert _snapshot_env() == env_antes


# --- REQ-2: perfil activo + marcador de onboarding (sin escribir) ------------


def test_estado_panel_usuario_conocido_devuelve_3x3(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.estado_panel(ruta, "ana", "macOS")
    assert res["conocido"] is True
    assert res["perfil"] == _ROOTS
    assert res["base_actual"] == "/Volumes/estudio/2026/CINE/TO_VFX"


def test_estado_panel_desconocido_marcador_sin_escribir(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", lambda b: {"conectado": False, "ruta": None, "detalle": "off"})
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    res = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert res["conocido"] is False
    assert res["perfil"] is None
    assert res["base_actual"] is None
    assert archivo.read_bytes() == antes


def test_detectar_desconocido_usuario_conocido_falso(tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    assert path_manager.detectar_desconocido(ruta, "ana") is False


def test_detectar_desconocido_legacy_es_desconocido(tmp_path):
    """Una entrada legacy (hosts/default) NO es perfil nuevo: cuenta como miss."""
    legacy = {"hosts": {"ws1": _ROOTS["COMP"]}, "default": _ROOTS["COMP"]}
    ruta = _escribir_store(tmp_path, {"ana": legacy})
    assert path_manager.detectar_desconocido(ruta, "ana") is True


def test_detectar_desconocido_miss_verdadero_sin_escribir(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    assert path_manager.detectar_desconocido(ruta, "nuevo") is True
    assert archivo.read_bytes() == antes


def test_detectar_desconocido_store_corrupto_no_raise(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert path_manager.detectar_desconocido(str(ruta), "ana") is True


def test_paridad_deteccion_vs_resolver_sin_escribir(tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    archivo = tmp_path / "nuke_profiles.json"
    antes = archivo.read_bytes()
    perfil = rutas_engine.leer_perfiles(ruta)["ana"]
    assert rutas_engine.detectar_forma_perfil(perfil) == "nuevo"
    assert perfil == rutas_engine.resolver_perfil("ana", ruta)
    assert path_manager.detectar_desconocido(ruta, "ana") is False
    assert archivo.read_bytes() == antes  # la deteccion nunca escribe (AD2)


# --- REQ-3: estado de unidad sobre la raiz del SO actual ----------------------


def test_estado_panel_unidad_conectada(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    registros = []

    def fake(base):
        registros.append(base)
        return _marcar_conectado(base)

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    res = path_manager.estado_panel(ruta, "ana", "macOS")
    assert res["unidad"] == {
        "conectado": True,
        "ruta": "/Volumes/estudio/2026/CINE/TO_VFX",
        "detalle": "Conectado.",
    }
    assert registros == ["/Volumes/estudio/2026/CINE/TO_VFX"]


def test_estado_panel_unidad_desconectada(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(
        entorno,
        "estado_unidad",
        lambda b: {"conectado": False, "ruta": None, "detalle": "Mount colgado (timeout 3s)."},
    )
    res = path_manager.estado_panel(ruta, "ana", "macOS")
    assert res["unidad"]["conectado"] is False
    assert res["unidad"]["ruta"] is None
    assert res["unidad"]["detalle"]


def test_estado_panel_desconocido_consulta_primera_candidata(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    registros = []

    def fake(base):
        registros.append(base)
        return {"conectado": False, "ruta": None, "detalle": "off"}

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    res = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert res["conocido"] is False
    assert registros == [entorno.rutas_base("macOS")[0]]


# --- REQ-4: cambio de base (READ-MERGE-WRITE, D7) ----------------------------


def test_cambio_base_mac_2027_rellena_slot_y_conserva_resto(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS, "pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    res = path_manager.preparar_cambio_base(
        "ana", ruta, "macOS", "/Volumes/estudio/2027"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2027/COMP"
    assert store["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2027/TO_VFX"
    assert store["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2027/FROM_VFX"
    # Otros SO y otros usuarios intactos (espacios independientes, AD1).
    assert store["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert store["ana"]["COMP"]["Linux"] == "/mnt/estudio/2026/CINE/COMP"
    assert store["pedro"] == _ROOTS
    assert res["perfil"]["COMP"]["macOS"] == "/Volumes/estudio/2027/COMP"
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert _snapshot_env() == env_antes


def test_cambio_base_legacy_lanza_error_claro_sin_reescribir(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    legacy = {"hosts": {"ws1": _ROOTS["COMP"]}, "default": _ROOTS["COMP"]}
    ruta = _escribir_store(tmp_path, {"ana": legacy})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    with pytest.raises(ValueError, match="No hay perfil activo"):
        path_manager.preparar_cambio_base("ana", ruta, "macOS", "/Volumes/estudio/2027")
    assert rutas_engine.leer_perfiles(ruta) == {"ana": legacy}  # sin escrituras


def test_cambio_base_desconocido_lanza_error_claro(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    with pytest.raises(ValueError):
        path_manager.preparar_cambio_base(
            "nuevo", ruta, "macOS", "/Volumes/estudio/2027"
        )


# --- REQ-5: onboarding (asegurar_perfil, slotting) ---------------------------


def test_onboarding_persiste_perfil_3x3(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    res = path_manager.preparar_onboarding(
        "nuevo", ruta, "/Volumes/estudio/2026", "macOS"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["COMP"]["macOS"] == "/Volumes/estudio/2026/COMP"
    assert store["nuevo"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2026/TO_VFX"
    assert store["nuevo"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert store["pedro"] == _ROOTS
    assert res["perfil"] == store["nuevo"]
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert _snapshot_env() == env_antes


def test_onboarding_slotting_linux(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_onboarding(
        "nuevo", ruta, "/mnt/estudio/2027", "Linux"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["COMP"]["Linux"] == "/mnt/estudio/2027/COMP"
    assert store["nuevo"]["TO_VFX"]["Linux"] == "/mnt/estudio/2027/TO_VFX"
    assert store["nuevo"]["FROM_VFX"]["Linux"] == "/mnt/estudio/2027/FROM_VFX"
    assert store["nuevo"]["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE/COMP"
    assert res["perfil"] == store["nuevo"]
    assert res["env"]["PROJECT_ROOT"] == "/mnt/estudio/2027"