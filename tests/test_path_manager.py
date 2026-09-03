"""Tests del helper puro del Path Manager — contrato usuario-solo (S3).

Cubre el helper ``SamanTools/ui/path_manager.py`` (TDD estricto, Qt-free)
con el esquema 3x3 de perfil-por-usuario (AD1/AD2): el hostname y la
escalera (exact/default/host ajeno) DESAPARECEN; un perfil pertenece al
usuario con raices independientes por espacio y por SO.

* REQ-1 — pureza y determinismo: sin nuke/PySide en el modulo, sin lectura ni
  mutacion de ``os.environ``; inputs identicos → salidas identicas.
* REQ-2 — lectura de perfil activo: usuario con forma nueva → perfil 3x3 y
  raiz del SO actual (primera raiz no-None); desconocido O legacy → marcador
  de onboarding SIN escribir el store y sin raise; ``estado_panel`` expone el
  flag ``legacy`` (regeneracion SOLO-LECTURA, spec S3) — una entrada con
  forma vieja se reporta, nunca se reescribe al detectar.
* REQ-3 — estado de unidad: ``entorno.estado_unidad`` consultado sobre la
  raiz del SO actual (perfil conocido) o sobre la primera candidata de
  ``entorno.rutas_base`` (sin perfil). ``preparar_seleccion_perfil`` consulta
  la unidad sobre la raiz del SO actual del perfil.
* REQ-4 — cambio de base POR ESPACIO (S3, D7): READ-MERGE-WRITE via
  ``guardar_perfiles``; la firma es ``(usuario, ruta_store, so, espacio,
  nueva_ruta, ruta_plato="")`` y SOLO se reemplaza el slot ``(espacio, so)``:
  los otros espacios, otros SO y otros usuarios quedan intactos (espacios
  independientes). Un ``espacio`` no canonico se interpreta como el modo
  TODOS (contrato transitorio del widget P2 — base de proyecto que rellena el
  slot del SO en los tres espacios, migrado en S4); un valor que no es ni
  espacio ni ruta lanza ``ValueError``. Sin perfil → ``ValueError``; env delta
  con ``PROJECT_ROOT``; ``os.environ`` intacto.
* REQ-5 — onboarding (D3): ``asegurar_perfil`` con slotting de la base
  inyectada; el store gana el perfil 3x3; env delta con la base;
  ``os.environ`` intacto.
* Perfil listing (spec S3): ``listar_perfiles`` devuelve los usuarios
  ordenados; store ausente/corrupto → ``[]`` sin lanzar.
* Perfil selection (spec S3): ``preparar_seleccion_perfil`` devuelve
  ``{"perfil", "env", "unidad"}`` sin escribir; usuario inexistente/legacy →
  ``ValueError`` (la seleccion no es creacion, nunca onboarding).

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

_LEGACY = {"hosts": {"ws1": _ROOTS["COMP"]}, "default": _ROOTS["COMP"]}


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


def _unidad_off(base):
    return {"conectado": False, "ruta": None, "detalle": "off"}


def _bytes_store(tmp_path):
    return (tmp_path / "nuke_profiles.json").read_bytes()


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


def test_firmas_publicas_sin_hostname():
    """AD2/spec S3: ninguna firma publica del helper recibe hostname."""
    import inspect

    publicas = [
        path_manager.estado_panel,
        path_manager.detectar_desconocido,
        path_manager.listar_perfiles,
        path_manager.preparar_seleccion_perfil,
        path_manager.preparar_cambio_base,
        path_manager.preparar_onboarding,
    ]
    for funcion in publicas:
        parametros = inspect.signature(funcion).parameters
        assert "hostname" not in parametros
        assert "host" not in parametros


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
    monkeypatch.setattr(entorno, "estado_unidad", _unidad_off)
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
    monkeypatch.setattr(entorno, "estado_unidad", _unidad_off)
    antes = _bytes_store(tmp_path)
    res = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert res["conocido"] is False
    assert res["perfil"] is None
    assert res["base_actual"] is None
    assert _bytes_store(tmp_path) == antes


def test_detectar_desconocido_usuario_conocido_falso(tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    assert path_manager.detectar_desconocido(ruta, "ana") is False


def test_detectar_desconocido_legacy_es_desconocido(tmp_path):
    """Una entrada legacy (hosts/default) NO es perfil nuevo: cuenta como miss."""
    ruta = _escribir_store(tmp_path, {"ana": _LEGACY})
    assert path_manager.detectar_desconocido(ruta, "ana") is True


def test_detectar_desconocido_miss_verdadero_sin_escribir(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    antes = _bytes_store(tmp_path)
    assert path_manager.detectar_desconocido(ruta, "nuevo") is True
    assert _bytes_store(tmp_path) == antes


def test_detectar_desconocido_store_corrupto_no_raise(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert path_manager.detectar_desconocido(str(ruta), "ana") is True


def test_paridad_deteccion_vs_resolver_sin_escribir(tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    antes = _bytes_store(tmp_path)
    perfil = rutas_engine.leer_perfiles(ruta)["ana"]
    assert rutas_engine.detectar_forma_perfil(perfil) == "nuevo"
    assert perfil == rutas_engine.resolver_perfil("ana", ruta)
    assert path_manager.detectar_desconocido(ruta, "ana") is False
    assert _bytes_store(tmp_path) == antes  # la deteccion nunca escribe (AD2)


# --- REQ-2b (S3): flag legacy SOLO-LECTURA en estado_panel -------------------


def test_estado_panel_legacy_flag_true_sin_escribir(monkeypatch, tmp_path):
    """Spec S3: una entrada con forma vieja se reporta con flag de
    regeneracion y el store NO cambia al detectar (flag read-only)."""
    ruta = _escribir_store(tmp_path, {"ana": _LEGACY})
    monkeypatch.setattr(entorno, "estado_unidad", _unidad_off)
    antes = _bytes_store(tmp_path)
    res = path_manager.estado_panel(ruta, "ana", "macOS")
    assert res["conocido"] is False
    assert res["legacy"] is True
    assert res["perfil"] is None
    assert _bytes_store(tmp_path) == antes


def test_estado_panel_legacy_flag_false_perfil_nuevo(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.estado_panel(ruta, "ana", "macOS")
    assert res["conocido"] is True
    assert res["legacy"] is False


def test_estado_panel_legacy_flag_false_usuario_ausente(monkeypatch, tmp_path):
    """Ausente no es legacy: el flag solo marca entradas con forma vieja."""
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _unidad_off)
    res = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert res["conocido"] is False
    assert res["legacy"] is False


# --- REQ-3: estado de unidad sobre la raiz del SO actual ---------------------


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
        return _unidad_off(base)

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    res = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert res["conocido"] is False
    assert registros == [entorno.rutas_base("macOS")[0]]


# --- Perfil listing (spec S3) ------------------------------------------------


def test_listar_perfiles_orden_estable(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS, "ana": _ROOTS, "zoe": _ROOTS})
    assert path_manager.listar_perfiles(ruta) == ["ana", "pedro", "zoe"]


def test_listar_perfiles_orden_independiente_de_insercion(tmp_path):
    ruta = _escribir_store(tmp_path, {"zoe": _ROOTS, "ana": _ROOTS})
    assert path_manager.listar_perfiles(ruta) == ["ana", "zoe"]


def test_listar_perfiles_store_ausente_vacio(tmp_path):
    ruta = str(tmp_path / "no_existe.json")
    assert path_manager.listar_perfiles(ruta) == []


def test_listar_perfiles_store_corrupto_vacio(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert path_manager.listar_perfiles(str(ruta)) == []


def test_listar_perfiles_store_sin_perfiles_vacio(tmp_path):
    ruta = _escribir_store(tmp_path, {})
    assert path_manager.listar_perfiles(ruta) == []


# --- Perfil selection (spec S3): nunca escribe, nunca crea -------------------


def test_seleccion_devuelve_perfil_env_unidad_sin_escribir(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    registros = []

    def fake(base):
        registros.append(base)
        return _marcar_conectado(base)

    monkeypatch.setattr(entorno, "estado_unidad", fake)
    antes = _bytes_store(tmp_path)
    env_antes = _snapshot_env()
    res = path_manager.preparar_seleccion_perfil(
        "ana", ruta, "macOS", "/Volumes/estudio/2026/CINE/COMP/EP_100/x.nk"
    )
    assert res["perfil"] == _ROOTS
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert res["env"]["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"
    assert res["env"]["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert res["unidad"]["conectado"] is True
    assert res["unidad"]["ruta"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert registros == ["/Volumes/estudio/2026/CINE/TO_VFX"]
    assert _bytes_store(tmp_path) == antes
    assert rutas_engine.leer_perfiles(ruta) == {"ana": _ROOTS}
    assert _snapshot_env() == env_antes


def test_seleccion_env_so_windows(monkeypatch, tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_seleccion_perfil(
        "ana", ruta, "Windows", "L:/VFX/2026/CINE/COMP/EP_100/x.nk"
    )
    assert res["env"]["PROJECT_ROOT"] == "L:/VFX/2026/CINE"
    assert res["env"]["PYTHON_COMP"] == "L:/VFX/2026/CINE/COMP"
    assert res["unidad"]["ruta"] == "L:/VFX/2026/CINE/TO_VFX"


def test_seleccion_usuario_inexistente_raise_sin_escribir(tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    antes = _bytes_store(tmp_path)
    with pytest.raises(ValueError, match="No hay perfil activo"):
        path_manager.preparar_seleccion_perfil("nuevo", ruta, "macOS")
    assert _bytes_store(tmp_path) == antes
    assert rutas_engine.leer_perfiles(ruta) == {"ana": _ROOTS}


def test_seleccion_legacy_raise_no_es_seleccion(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _LEGACY})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    antes = _bytes_store(tmp_path)
    with pytest.raises(ValueError, match="No hay perfil activo"):
        path_manager.preparar_seleccion_perfil("ana", ruta, "macOS")
    assert rutas_engine.leer_perfiles(ruta) == {"ana": _LEGACY}
    assert _bytes_store(tmp_path) == antes


# --- REQ-4 (S3): cambio de base POR ESPACIO (READ-MERGE-WRITE, D7) -----------


def test_cambio_base_por_espacio_cambia_solo_ese_slot(monkeypatch, tmp_path):
    """Spec S3: ``preparar_cambio_base("ana", store, "macOS", "COMP", ...)``
    reemplaza SOLO el slot (COMP, macOS). Los otros espacios (TO_VFX,
    FROM_VFX), otros SO y ``"pedro"`` quedan intactos; el env delta corta
    ``PROJECT_ROOT`` del plato."""
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS, "pedro": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    env_antes = _snapshot_env()
    res = path_manager.preparar_cambio_base(
        "ana",
        ruta,
        "macOS",
        "COMP",
        "/Volumes/estudio/2026/CINE2/COMP",
        ruta_plato="/Volumes/estudio/2026/CINE2/COMP/EP_100/x.nk",
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE2/COMP"
    assert store["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert store["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2026/CINE/FROM_VFX"
    assert store["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert store["ana"]["COMP"]["Linux"] == "/mnt/estudio/2026/CINE/COMP"
    assert store["pedro"] == _ROOTS
    assert res["perfil"]["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE2/COMP"
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE2"
    assert res["env"]["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE2/COMP"
    assert _snapshot_env() == env_antes


def test_cambio_base_por_espacio_otro_espacio_y_so_windows(monkeypatch, tmp_path):
    """Triangulacion: el slot (FROM_VFX, Windows) cambia; el resto intacto."""
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_cambio_base(
        "ana",
        ruta,
        "Windows",
        "FROM_VFX",
        "M:/VFX/2026/CINE/FROM_VFX",
        ruta_plato="M:/VFX/2026/CINE/FROM_VFX/EP_200/y.nk",
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["FROM_VFX"]["Windows"] == "M:/VFX/2026/CINE/FROM_VFX"
    assert store["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert store["ana"]["TO_VFX"]["Windows"] == "L:/VFX/2026/CINE/TO_VFX"
    assert store["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2026/CINE/FROM_VFX"
    assert res["env"]["PROJECT_ROOT"] == "M:/VFX/2026/CINE"


def test_cambio_base_todos_compat_widget_antes_de_s4(monkeypatch, tmp_path):
    """Contrato P1/P2 (widget congelado hasta S4): la llamada antigua con una
    base de proyecto rellena el slot del SO en los TRES espacios."""
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    res = path_manager.preparar_cambio_base(
        "ana", ruta, "macOS", "/Volumes/estudio/2027"
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2027/COMP"
    assert store["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2027/TO_VFX"
    assert store["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2027/FROM_VFX"
    assert store["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert res["env"]["PROJECT_ROOT"] == "/Volumes/estudio/2027"


def test_cambio_base_espacio_no_canonico_ni_ruta_lanza(tmp_path):
    ruta = _escribir_store(tmp_path, {"ana": _ROOTS})
    with pytest.raises(ValueError, match="Espacio"):
        path_manager.preparar_cambio_base("ana", ruta, "macOS", "OTRO", "/x/COMP")


def test_cambio_base_legacy_lanza_error_claro_sin_reescribir(monkeypatch, tmp_path):
    from SamanTools.core import rutas_engine

    ruta = _escribir_store(tmp_path, {"ana": _LEGACY})
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    antes = _bytes_store(tmp_path)
    with pytest.raises(ValueError, match="No hay perfil activo"):
        path_manager.preparar_cambio_base(
            "ana", ruta, "macOS", "COMP", "/Volumes/estudio/2027/COMP"
        )
    assert rutas_engine.leer_perfiles(ruta) == {"ana": _LEGACY}
    assert _bytes_store(tmp_path) == antes


def test_cambio_base_desconocido_lanza_error_claro(tmp_path):
    ruta = _escribir_store(tmp_path, {"pedro": _ROOTS})
    with pytest.raises(ValueError, match="No hay perfil activo"):
        path_manager.preparar_cambio_base(
            "nuevo", ruta, "macOS", "COMP", "/Volumes/estudio/2027/COMP"
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