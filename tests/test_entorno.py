"""
Tests de SamanTools.core.entorno (subset puro porteado de V1).

entorno es puro (sin nuke) y testeable con pytest. Este archivo porta el
subset PURO de tests de V1 (lineas 37-267 de tests/test_entorno.py de
saman-nuke-tools), con rutas reales del estudio neutralizadas a rutas
ficticias (/Volumes/estudio/2026, L:/VFX/2026, /mnt/estudio/2026, CINE).
Los tests de integracion con el stub de nuke (lineas 279-534 de V1) estan
DIFERIDOS: no se portan (spec core-purity-guard).

No se cubre el timeout REAL (lento/flaky): se mockea subprocess.run.
"""

import os
import subprocess

import pytest

from SamanTools.core import entorno


@pytest.fixture(autouse=True)
def _cache_estado_limpio():
    """Cache a nivel de modulo: purga antes y despues de cada test."""
    entorno._cache.clear()
    yield
    entorno._cache.clear()


# --------------------------------------------------------------------------
# detectar_so / sufijo_so / usuario_activo
# --------------------------------------------------------------------------


def test_detectar_so_devuelve_so_valido():
    assert entorno.detectar_so() in ("macOS", "Windows", "Linux")


@pytest.mark.parametrize(
    "so,sufijo,usuario",
    [
        ("macOS", "MAC", "MacServer"),
        ("Windows", "WINDOWS", "Windows"),
        ("Linux", "ARTIST", "Artist"),
    ],
)
def test_tabla_so_sufijo_usuario(so, sufijo, usuario):
    assert entorno.sufijo_so(so) == sufijo
    assert entorno.usuario_activo(so) == usuario


# --------------------------------------------------------------------------
# rutas_base
# --------------------------------------------------------------------------


def test_rutas_base_macos():
    r = entorno.rutas_base("macOS")
    assert r[0] == "/Volumes/estudio/2026"
    assert "/Volumes/estudioCloud/2026" in r


def test_rutas_base_linux():
    r = entorno.rutas_base("Linux")
    assert r[0] == "/mnt/estudio/2026"


def test_rutas_base_extra_va_primera():
    r = entorno.rutas_base("macOS", extra="/miespacio/prueba")
    assert r[0] == "/miespacio/prueba"
    assert "/Volumes/estudio/2026" in r


def test_rutas_base_windows_escanea_letras(monkeypatch):
    reales = {"L:/VFX/2026", "Z:/VFX/2026", "T:/VFX/2026"}

    def falso_isdir(p):
        return p in reales

    monkeypatch.setattr(entorno.os.path, "isdir", falso_isdir)
    r = entorno.rutas_base("Windows")
    assert r[0] == "L:/VFX/2026"
    assert r.count("L:/VFX/2026") == 1  # la L no se duplica
    assert "Z:/VFX/2026" in r
    assert "T:/VFX/2026" in r


# --------------------------------------------------------------------------
# estado_unidad
# --------------------------------------------------------------------------


def test_estado_unidad_conectado(tmp_path):
    ruta = str(tmp_path)
    res = entorno.estado_unidad(ruta)
    assert res["conectado"] is True
    assert res["ruta"] == ruta
    assert res["detalle"]


def test_estado_unidad_ruta_inexistente():
    res = entorno.estado_unidad("/ruta/que/no/existe/SamanToolsXYZ987")
    assert res["conectado"] is False
    assert res["ruta"] is None
    assert res["detalle"]


def test_estado_unidad_vacia():
    res = entorno.estado_unidad("")
    assert res["conectado"] is False
    assert res["ruta"] is None


def test_estado_unidad_none():
    assert entorno.estado_unidad(None)["conectado"] is False


def test_estado_unidad_timeout_se_considera_desconectado(monkeypatch):
    def _colgar(*a, **k):
        raise subprocess.TimeoutExpired(["ls", "-d", "/ruta/colgada"], 3)

    monkeypatch.setattr(entorno.subprocess, "run", _colgar)
    res = entorno.estado_unidad("/Volumes/estudio/2026")
    assert res["conectado"] is False
    assert res["ruta"] is None
    assert "timeout" in res["detalle"].lower()


def test_estado_unidad_usa_cache(monkeypatch, tmp_path):
    ruta = str(tmp_path)
    llamadas = []
    real = entorno._verificar_ruta

    def contar(p):
        llamadas.append(p)
        return real(p)

    monkeypatch.setattr(entorno, "_verificar_ruta", contar)
    entorno.estado_unidad(ruta)
    entorno.estado_unidad(ruta)
    assert len(llamadas) == 1  # la segunda consulta sale de cache


# --------------------------------------------------------------------------
# primera_ruta_disponible
# --------------------------------------------------------------------------


def test_primera_ruta_disponible_extra(tmp_path):
    ruta = str(tmp_path)
    assert entorno.primera_ruta_disponible("macOS", extra=ruta) == ruta


def test_primera_ruta_disponible_ninguna(monkeypatch):
    monkeypatch.setattr(
        entorno, "rutas_base", lambda so, extra=None: ["/no/existe/SamanTools/nope"]
    )
    assert entorno.primera_ruta_disponible("macOS") is None


# --------------------------------------------------------------------------
# reconstruir_rutas
# --------------------------------------------------------------------------


def test_reconstruir_rutas_genera_9_claves():
    r = entorno.reconstruir_rutas("/Volumes/estudio/2026", "CINE")
    assert len(r) == 9
    assert r["TO_VFX_SERVER_MAC"] == "/Volumes/estudio/2026/CINE/TO_VFX/"
    assert r["comp_SERVER_MAC"] == "/Volumes/estudio/2026/CINE/COMP/"
    assert r["FROM_VFX_SERVER_MAC"] == "/Volumes/estudio/2026/CINE/FROM_VFX/"
    assert r["TO_VFX_SERVER_WINDOWS"] == "/Volumes/estudio/2026/CINE/TO_VFX/"
    assert r["comp_SERVER_ARTIST"] == "/Volumes/estudio/2026/CINE/COMP/"
    assert r["FROM_VFX_SERVER_ARTIST"] == "/Volumes/estudio/2026/CINE/FROM_VFX/"


def test_reconstruir_rutas_windows_forward_slashes():
    r = entorno.reconstruir_rutas("L:/VFX/2026", "CINE")
    assert r["TO_VFX_SERVER_WINDOWS"] == "L:/VFX/2026/CINE/TO_VFX/"
    assert "\\" not in r["TO_VFX_SERVER_WINDOWS"]


def test_reconstruir_rutas_limpia_slashes_y_espacios():
    r = entorno.reconstruir_rutas("/Volumes/estudio/2026/", " CINE ")
    assert r["TO_VFX_SERVER_MAC"] == "/Volumes/estudio/2026/CINE/TO_VFX/"


def test_reconstruir_rutas_claves_exactas_de_los_knobs():
    r = entorno.reconstruir_rutas("L:/VFX/2026", "CINE")
    esperadas = {
        "TO_VFX_SERVER_MAC",
        "comp_SERVER_MAC",
        "FROM_VFX_SERVER_MAC",
        "TO_VFX_SERVER_WINDOWS",
        "comp_SERVER_WINDOWS",
        "FROM_VFX_SERVER_WINDOWS",
        "TO_VFX_SERVER_ARTIST",
        "comp_SERVER_ARTIST",
        "FROM_VFX_SERVER_ARTIST",
    }
    assert set(r.keys()) == esperadas


# --------------------------------------------------------------------------
# proyecto_desde_ruta
# --------------------------------------------------------------------------


def test_proyecto_desde_ruta_cine_mac():
    ruta = "/Volumes/estudio/2026/CINE/COMP/EP_100/CINE_100_000_00000_comp_SAMAN_V01.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="/Volumes/estudio/2026") == "CINE"


def test_proyecto_desde_ruta_otro_proyecto():
    ruta = "/Volumes/estudio/2026/CINE/COMP/EP_001/CINE_001_010_comp_V01.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="/Volumes/estudio/2026") == "CINE"


def test_proyecto_desde_ruta_windows_forward_slashes():
    ruta = "L:/VFX/2026/CINE/COMP/EP_100/CINE_100_000_00000_comp_SAMAN_V01.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="L:/VFX/2026") == "CINE"


def test_proyecto_desde_ruta_acepta_backslashes():
    ruta = r"L:\VFX\2026\CINE\COMP\EP_100\CINE_100_000_00000_comp_SAMAN_V01.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="L:/VFX/2026") == "CINE"


def test_proyecto_desde_ruta_sin_base_usa_candidatas(monkeypatch):
    # Sin base: prueba contra rutas_base del SO detectado.
    monkeypatch.setattr(
        entorno,
        "rutas_base",
        lambda so, extra=None: ["/Volumes/estudio/2026", "/mnt/estudio/2026"],
    )
    ruta = "/Volumes/estudio/2026/CINE/COMP/EP_100/foo.nk"
    assert entorno.proyecto_desde_ruta(ruta) == "CINE"


def test_proyecto_desde_ruta_fuera_de_base_devuelve_none():
    ruta = "/Volumes/otro/2026/CINE/COMP/EP_100/foo.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="/Volumes/estudio/2026") is None


def test_proyecto_desde_ruta_ruta_es_la_base_devuelve_none():
    assert (
        entorno.proyecto_desde_ruta(
            "/Volumes/estudio/2026", base="/Volumes/estudio/2026"
        )
        is None
    )


def test_proyecto_desde_ruta_vacia_devuelve_none():
    assert entorno.proyecto_desde_ruta("", base="/Volumes/estudio/2026") is None
    assert entorno.proyecto_desde_ruta(None, base="/Volumes/estudio/2026") is None


def test_proyecto_desde_ruta_prefijo_parcial_no_confunde():
    # 'estudio2026' no es la base 'estudio' + '2026': startswith(b + '/') lo evita.
    ruta = "/Volumes/estudio2026/CINE/COMP/foo.nk"
    assert entorno.proyecto_desde_ruta(ruta, base="/Volumes/estudio/2026") is None


def test_proyecto_desde_ruta_con_base_con_slash_final():
    ruta = "/Volumes/estudio/2026/CINE/COMP/EP_100/foo.nk"
    assert (
        entorno.proyecto_desde_ruta(ruta, base="/Volumes/estudio/2026/") == "CINE"
    )


# --------------------------------------------------------------------------
# raiz_proyecto_desde_ruta (corte estructural por marcador, AD4)
# --------------------------------------------------------------------------


def test_raiz_proyecto_corte_en_comp():
    """Spec: cut at COMP — la raiz es la porcion previa al primer marcador."""
    ruta = "/Volumes/estudio/2026/CINE/COMP/EP_100/foo.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) == "/Volumes/estudio/2026/CINE"


def test_raiz_proyecto_corte_en_from_vfx_otra_base():
    """Spec: cut at FROM_VFX — camion distinto (Linux/2027) triangula la rama."""
    ruta = "/mnt/estudio/2027/CINE/FROM_VFX/ep_050.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) == "/mnt/estudio/2027/CINE"


def test_raiz_proyecto_sin_marcador_devuelve_none():
    """Spec: no marker segment -> None."""
    ruta = "/Volumes/estudio/2026/CINE/artwork/x.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) is None


def test_raiz_proyecto_windows_normaliza_slashes():
    """Spec: Windows backslashes -> forward slashes, corte en TO_VFX."""
    ruta = r"L:\VFX\2026\CINE\TO_VFX\ep.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) == "L:/VFX/2026/CINE"


def test_raiz_proyecto_base_sola_devuelve_none():
    """La base en si no tiene segmento marcador: sin corte -> None."""
    assert entorno.raiz_proyecto_desde_ruta("/Volumes/estudio/2026") is None


def test_raiz_proyecto_saman_no_es_marcador():
    """'.saman' NO es marcador (AD4): una ruta dentro de .saman no corta."""
    ruta = "/Volumes/estudio/2026/CINE/.saman/nuke_profiles.json"
    assert entorno.raiz_proyecto_desde_ruta(ruta) is None


def test_raiz_proyecto_marcador_case_insensitive():
    """Marker match es case-insensitive: 'comp' == 'COMP'."""
    ruta = "/Volumes/estudio/2026/CINE/comp/EP_100/foo.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) == "/Volumes/estudio/2026/CINE"


def test_raiz_proyecto_marcador_debe_ser_segmento_entero():
    """Boundary de segmento: 'COMPlex' NO es el marcador 'COMP'."""
    ruta = "/Volumes/estudio/2026/CINE/COMPlex/x.nk"
    assert entorno.raiz_proyecto_desde_ruta(ruta) is None


def test_raiz_proyecto_vacia_devuelve_none():
    assert entorno.raiz_proyecto_desde_ruta("") is None
    assert entorno.raiz_proyecto_desde_ruta(None) is None


def test_raiz_proyecto_trailing_separadores_se_limpian():
    """Separadores finales se limpian antes del corte (resultado sin / final)."""
    ruta = "/Volumes/estudio/2026/CINE/COMP//"
    assert entorno.raiz_proyecto_desde_ruta(ruta) == "/Volumes/estudio/2026/CINE"


def test_raiz_proyecto_marcador_en_primera_posicion_devuelve_none():
    """El marcador como PRIMER segmento no deja raiz previa: None."""
    assert entorno.raiz_proyecto_desde_ruta("/COMP/ep.nk") is None