"""Tests de la logica pura del desinstalador de Script Editor (V2).

El desinstalador separa la logica pura (sin Nuke) de la capa de
consentimiento (nuke.ask / nuke.message). Aquí solo se testea la logica
pura con `tmp_path`; la parte que usa nuke (0%) no se testea, patron V1
igual que en test_instalar_script_editor.py.

Además se incluyen guardias anti-fuga: el desinstalador no debe contener
el placeholder `TU_USUARIO`, `import nuke` solo puede aparecer dentro de
funciones (nunca a nivel de modulo), y el marcador V2 debe ser el mismo
que declara el bootstrap.
"""

import re
from pathlib import Path

import desinstalar_script_editor as desinstalador

_RAIZ = Path(__file__).resolve().parent.parent


# --- _limpiar_checkout_y_respaldos -------------------------------------------


def test_limpiar_borra_checkout_y_respaldos(tmp_path):
    padre = tmp_path / "nuke"
    padre.mkdir()
    (padre / "SamanTools").mkdir()
    (padre / "SamanTools.desinstalado_20240101").mkdir()
    (padre / "otro_script.py").write_text("print('ok')\n", encoding="utf-8")

    hechos = desinstalador._limpiar_checkout_y_respaldos(str(padre), "SamanTools")

    assert not (padre / "SamanTools").exists()
    assert not (padre / "SamanTools.desinstalado_20240101").exists()
    assert (padre / "otro_script.py").exists()
    assert any("SamanTools" in h for h in hechos)
    assert any("desinstalado_" in h for h in hechos)
    assert not any("otro_script" in h for h in hechos)


def test_limpiar_solo_respaldos_sin_checkout(tmp_path):
    padre = tmp_path / "nuke"
    padre.mkdir()
    (padre / "SamanTools.desinstalado_20240101").mkdir()

    hechos = desinstalador._limpiar_checkout_y_respaldos(str(padre), "SamanTools")

    assert not (padre / "SamanTools.desinstalado_20240101").exists()
    assert len(hechos) == 1


def test_limpiar_sin_nada_devuelve_vacio(tmp_path):
    padre = tmp_path / "nuke"
    padre.mkdir()
    (padre / "menu.py").write_text("print('ajeno')\n", encoding="utf-8")

    hechos = desinstalador._limpiar_checkout_y_respaldos(str(padre), "SamanTools")

    assert hechos == []


# --- _borrar_bootstrap_si_marcador -------------------------------------------


def test_borrar_bootstrap_con_marcador_v2(tmp_path):
    menu = tmp_path / "menu.py"
    menu.write_text(
        "print('hola')\n# SamanTools V2 bootstrap\n", encoding="utf-8"
    )

    hechos = desinstalador._borrar_bootstrap_si_marcador(str(menu), "SamanTools V2 bootstrap")

    assert not menu.exists()
    assert any("Eliminado: menu.py" in h for h in hechos)


def test_borrar_bootstrap_no_toca_sin_marcador(tmp_path):
    menu = tmp_path / "menu.py"
    menu.write_text("print('script ajeno')\n", encoding="utf-8")

    hechos = desinstalador._borrar_bootstrap_si_marcador(str(menu), "SamanTools V2 bootstrap")

    assert menu.exists()
    assert any("no parece ser el bootstrap" in h for h in hechos)


def test_borrar_bootstrap_no_toca_v1(tmp_path):
    menu = tmp_path / "menu.py"
    menu.write_text(
        "# bootstrap de artista\nprint('V1')\n", encoding="utf-8"
    )

    hechos = desinstalador._borrar_bootstrap_si_marcador(str(menu), "SamanTools V2 bootstrap")

    assert menu.exists()
    assert any("no parece ser el bootstrap" in h for h in hechos)


def test_borrar_bootstrap_sin_archivo_no_informa_hecho(tmp_path):
    hechos = desinstalador._borrar_bootstrap_si_marcador(
        str(tmp_path / "inexistente.py"), "SamanTools V2 bootstrap"
    )
    assert hechos == []


# --- _desinstalar (integracion) ----------------------------------------------


def test_desinstalar_integrado_borra_todo(tmp_path):
    padre = tmp_path / "nuke"
    padre.mkdir()
    (padre / "SamanTools").mkdir()
    menu = padre / "menu.py"
    menu.write_text("# SamanTools V2 bootstrap\n", encoding="utf-8")

    hechos = desinstalador._desinstalar(str(padre), "SamanTools", str(menu), "SamanTools V2 bootstrap")

    assert not (padre / "SamanTools").exists()
    assert not menu.exists()
    assert any("SamanTools" in h for h in hechos)
    assert any("Eliminado: menu.py" in h for h in hechos)


def test_desinstalar_integrado_no_toca_menu_ajeno(tmp_path):
    padre = tmp_path / "nuke"
    padre.mkdir()
    (padre / "SamanTools").mkdir()
    menu = padre / "menu.py"
    menu.write_text("print('otro')\n", encoding="utf-8")

    hechos = desinstalador._desinstalar(str(padre), "SamanTools", str(menu), "SamanTools V2 bootstrap")

    assert not (padre / "SamanTools").exists()
    assert menu.exists()
    assert any("no parece ser el bootstrap" in h for h in hechos)


# --- Guardias anti-fuga y pureza de import -----------------------------------


def test_desinstalador_sin_placeholder_tu_usuario():
    codigo = (_RAIZ / "desinstalar_script_editor.py").read_text(encoding="utf-8")
    assert "TU_USUARIO" not in codigo


def test_marcador_v2_identico_al_bootstrap():
    codigo = (_RAIZ / "desinstalar_script_editor.py").read_text(encoding="utf-8")
    assert desinstalador.MARCADOR == "SamanTools V2 bootstrap"
    bootstrap = (_RAIZ / "bootstrap" / "menu.py").read_text(encoding="utf-8")
    assert desinstalador.MARCADOR in bootstrap


def test_nuke_solo_se_importa_dentro_de_funciones():
    codigo = (_RAIZ / "desinstalar_script_editor.py").read_text(encoding="utf-8")
    violaciones = [
        linea
        for linea in codigo.splitlines()
        if re.match(r"^(import\s+nuke\b|from\s+nuke\b)", linea)
    ]
    assert violaciones == []


def test_import_headless_sin_nuke(tmp_path):
    # la suite corre en maquinas sin Nuke: importar la logica pura es la prueba
    assert desinstalador._limpiar_checkout_y_respaldos(str(tmp_path), "SamanTools") == []