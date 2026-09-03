"""Tests del dialogo fino del Path Manager (cambio path-manager-panel, slice P2).

Cubre el widget ``SamanTools/ui/path_manager_panel.py`` (TDD estricto, pytest-qt):

* REQ-1 (escenario "profile and status rendered from helper data") — el dialogo
  con un perfil conocido renderiza la raiz ficticia del SO actual y el estado
  de unidad conectado, sin mutar ``os.environ``.
* REQ-4 (escenario "snapshot unchanged on cancel") — abrir, renderizar y
  cancelar (Cerrar) deja ``os.environ`` intacto; ademas el codigo del widget
  NO muta ``os.environ`` por su cuenta: la propagacion del env pasa SOLO por
  ``injector.cachear_env`` + ``injector.aplicar_entorno``.
* REQ-2 (escenario "new user submits base and env propagates") — el submit del
  onboarding llama UNA vez a ``asegurar_perfil`` con la base del formulario y
  aplica el env devuelto via injector; ``os.environ["PROJECT_ROOT"]`` queda en
  la base ficticia.
* REQ-3 (escenario "change base re-applies env") — el cambio de base persiste
  via helper y re-aplica el env a la base 2027 via injector.
* REQ-5 (escenarios "no GUI degrades silently") — ``abrir_dialogo()`` sin
  sesion grafica (``nuke.GUI`` falso) o sin PySide disponible degrada en
  silencio: nunca lanza y no crea ventana.

Todas las rutas son ficticias (``/Volumes/estudio/2026``, ``L:/VFX/2026``,
``/mnt/estudio/2026``); ninguna ruta real del estudio aparece en fixtures.
"""

import json
import os

import pytest

if os.environ.get("QT_QPA_PLATFORM") is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

pytest.importorskip("PySide6")

from SamanTools.core import entorno  # noqa: E402
from SamanTools.core import rutas_engine  # noqa: E402
from SamanTools.ui import injector  # noqa: E402
from SamanTools.ui import path_manager  # noqa: E402
from SamanTools.ui import path_manager_panel  # noqa: E402

_ROOTS = {
    "macOS": "/Volumes/estudio/2026",
    "Windows": "L:/VFX/2026",
    "Linux": "/mnt/estudio/2026",
}


@pytest.fixture(autouse=True)
def _restaurar_estado(monkeypatch):
    """Aisla cada test: entorno, ``__main__`` e inyector sin efectos residuales.

    Los tests de submit aplican env real (``injector.aplicar_entorno``) que
    muta ``os.environ`` y ``__main__``; esta fixture restaura ambos y el cache
    del injector para no contaminar el resto de la suite.
    """
    import __main__

    env_antes = dict(os.environ)
    main_antes = {k: v for k, v in vars(__main__).items() if k.isupper()}
    injector._env_cache = None
    injector._env_inyectado = False
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


class _NukeFake:
    """Modulo nuke fake minimo: GUI + message con grabacion (patron test_bootstrap)."""

    def __init__(self, gui=True):
        self.GUI = gui
        self.messages = []

    def message(self, texto):
        self.messages.append(texto)


def _escribir_store(tmp_path, perfiles):
    """Escribe un store ficticio y devuelve su ruta como string."""
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text(
        json.dumps({"perfiles": perfiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(ruta)


def _marcar_conectado(base):
    return {"conectado": True, "ruta": base, "detalle": "Conectado."}


def _spy_aplicar_env(monkeypatch):
    """Envuelve ``cachear_env``/``aplicar_entorno`` grabando los dicts recibidos.

    Devuelve ``(ruta_cache, ruta_aplicados)``; las listas guardan COPY del env
    recibido. Los wrappers delegan en la implementacion real para que
    ``os.environ`` y el cache del injector sigan funcionando.
    """
    cacheados = []
    aplicados = []
    real_cachear = injector.cachear_env
    real_aplicar = injector.aplicar_entorno

    def spy_cachear(env):
        cacheados.append(dict(env))
        return real_cachear(env)

    def spy_aplicar(env):
        aplicados.append(dict(env))
        return real_aplicar(env)

    monkeypatch.setattr(injector, "cachear_env", spy_cachear)
    monkeypatch.setattr(injector, "aplicar_entorno", spy_aplicar)
    return cacheados, aplicados


# ---------------------------------------------------------------------------
# REQ-1 (2.1): render de datos del helper + environment intacto
# ---------------------------------------------------------------------------


def test_dialogo_conocido_muestra_raiz_y_estado(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    env_antes = dict(os.environ)

    estado = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(estado, "ana", "ws1", ruta, "macOS")
    qtbot.addWidget(dialogo)

    assert dialogo.label_perfil.text() == "Raiz actual: /Volumes/estudio/2026"
    assert dialogo.label_unidad.text() == "Unidad: Conectado."
    assert dict(os.environ) == env_antes


def test_dialogo_abrir_y_cancelar_no_muta_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    estado = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    env_antes = dict(os.environ)

    dialogo = path_manager_panel.PathManagerDialog(estado, "ana", "ws1", ruta, "macOS")
    qtbot.addWidget(dialogo)

    dialogo.boton_cerrar.click()  # cancelar sin submit

    assert dict(os.environ) == env_antes


def test_panel_env_solo_via_injector():
    """REQ-4: el widget nunca toca ``os.environ`` directo (solo injector)."""
    with open(path_manager_panel.__file__, "r", encoding="utf-8") as fh:
        texto = fh.read()
    assert "os.environ" not in texto
    assert "aplicar_entorno" in texto  # el env se propaga por el injector
    assert "injector.aplicar_entorno" in texto


# ---------------------------------------------------------------------------
# REQ-2 (2.3): onboarding -> asegurar_perfil una vez + env aplicado
# ---------------------------------------------------------------------------


def test_onboarding_submit_asegura_una_vez_y_aplica_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": {"hosts": {"ws2": _ROOTS}}})

    aseguraron = []
    real_asegurar = rutas_engine.asegurar_perfil

    def spy_asegurar(usuario, hostname, ruta_store, **kwargs):
        aseguraron.append((usuario, hostname, kwargs))
        return real_asegurar(usuario, hostname, ruta_store, **kwargs)

    monkeypatch.setattr(rutas_engine, "asegurar_perfil", spy_asegurar)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "nuevo", "pc9", "macOS")
    assert estado["conocido"] is False
    dialogo = path_manager_panel.PathManagerDialog(estado, "nuevo", "pc9", ruta, "macOS")
    qtbot.addWidget(dialogo)

    assert dialogo.label_perfil.text() == "Onboarding: defina la base del proyecto"

    dialogo.campo_base.setText("/Volumes/estudio/2026")
    dialogo.boton_onboarding.click()

    assert len(aseguraron) == 1
    assert aseguraron[0][0] == "nuevo"
    assert aseguraron[0][1] == "pc9"
    assert aseguraron[0][2]["base"] == "/Volumes/estudio/2026"
    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert cacheados[-1] == aplicados[-1]
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["nuevo"]["hosts"]["pc9"]["macOS"] == "/Volumes/estudio/2026"


# ---------------------------------------------------------------------------
# REQ-3 (2.3): cambio de base -> env re-aplicado a la base nueva
# ---------------------------------------------------------------------------


def test_cambio_base_reaplica_env_2027(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": {"hosts": {"ws1": _ROOTS}}})
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "ws1", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(estado, "ana", "ws1", ruta, "macOS")
    qtbot.addWidget(dialogo)

    dialogo.campo_base.setText("/Volumes/estudio/2027")
    dialogo.boton_cambio.click()

    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["hosts"]["ws1"]["macOS"] == "/Volumes/estudio/2027"
    assert guardado["ana"]["hosts"]["ws1"]["Windows"] == "L:/VFX/2026"


# ---------------------------------------------------------------------------
# REQ-5 (2.3): abrir_dialogo degrade headless
# ---------------------------------------------------------------------------


def test_abrir_dialogo_sin_gui_no_levanta(monkeypatch):
    fake = _NukeFake(gui=False)
    res = path_manager_panel.abrir_dialogo(
        nuke_mod=fake, usuario="ana", hostname="ws1", ruta_store="x", so="macOS"
    )
    assert res is None
    assert fake.messages == []
    assert "PROJECT_ROOT" not in os.environ


def test_abrir_dialogo_sin_pyside_no_levanta(monkeypatch):
    import builtins
    import importlib
    import sys

    # Reimportar el modulo con PySide bloqueado: la capa de import degrada y
    # ``abrir_dialogo`` sigue invocable sin levantar (REQ-5).
    monkeypatch.delitem(sys.modules, "SamanTools.ui.path_manager_panel", raising=False)
    original_import = builtins.__import__

    def _bloquear_pyside(nombre, *args, **kwargs):
        if nombre == "PySide2" or nombre == "PySide6" or nombre.startswith("PySide"):
            raise ImportError("PySide bloqueado para el test")
        return original_import(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _bloquear_pyside)

    modulo = importlib.import_module("SamanTools.ui.path_manager_panel")
    fake = _NukeFake(gui=True)
    res = modulo.abrir_dialogo(
        nuke_mod=fake, usuario="ana", hostname="ws1", ruta_store="x", so="macOS"
    )
    assert res is None
    assert fake.messages == []