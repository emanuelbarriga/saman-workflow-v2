"""Tests del dialogo Path Manager — slice S4 (widget combo + apply-on-select).

Cubre el widget ``SamanTools/ui/path_manager_panel.py`` (TDD estricto,
pytest-qt) sobre el contrato usuario-solo de perfil-por-usuario (AD2): el
dialogo consume DATOS del helper (estado, unidad, LISTA de perfiles) y NUNCA
computa perfiles ni escribe el entorno por su cuenta.

* REQ-1 (escenario "profile and status rendered from helper data") — el
  dialogo con un perfil conocido renderiza la raiz ficticia del SO actual, el
  estado de unidad conectado y el combo de perfiles, sin mutar ``os.environ``.
* Combo (ADDED "Profile selector combo") — rellenado al abrir
  (``listar_perfiles`` via ``abrir_dialogo``), preseleccion del usuario, store
  vacio -> combo vacio + onboarding; seleccion -> env + refresco de Reads;
  ``ValueError`` stale sin env parcial; flag legacy -> aviso de regeneracion.
* REQ-2 (escenario "new user submits base and env propagates") — el submit del
  onboarding llama UNA vez a ``asegurar_perfil`` con la base del formulario y
  aplica el env devuelto via injector.
* REQ-3 (escenario "change base re-applies env") — el cambio de base por
  ESPACIO (S4) persiste via helper la raiz del slot (espacio, so) y re-aplica
  el env via injector; otras raices intactas.
* REQ-5 (escenarios "no GUI degrades silently") — ``abrir_dialogo()`` sin
  sesion grafica o sin PySide degrada en silencio.
* S5 para nombres editables — onboarding con campo de nombre pre-llenado con
  el usuario (editable): crea el perfil con ESE nombre y deja la seleccion
  por estacion; nombre vacio no crea.
* S5 renombrar — re-key conserva las 9 raices y refresca el combo; nombre
  existente se informa sin romper.
* S5 preseleccion por estacion — seleccion guardada > usuario > primer
  perfil; aplicar una seleccion guarda la eleccion local.

Todas las rutas son ficticias (``/Volumes/estudio/2026/CINE/...``,
``L:/VFX/2026/CINE/...``, ``/mnt/estudio/2026/CINE/...``).
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

_ROOT_2026 = {
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

# Raices del 2027 para triangular el apply-on-select (perfil distinto -> env
# distinto y cambio de proyecto en los Reads).
_ROOT_2027 = {
    "TO_VFX": {
        "macOS": "/Volumes/estudio/2027/CINE2/TO_VFX",
        "Windows": "L:/VFX/2027/CINE2/TO_VFX",
        "Linux": "/mnt/estudio/2027/CINE2/TO_VFX",
    },
    "COMP": {
        "macOS": "/Volumes/estudio/2027/CINE2/COMP",
        "Windows": "L:/VFX/2027/CINE2/COMP",
        "Linux": "/mnt/estudio/2027/CINE2/COMP",
    },
    "FROM_VFX": {
        "macOS": "/Volumes/estudio/2027/CINE2/FROM_VFX",
        "Windows": "L:/VFX/2027/CINE2/FROM_VFX",
        "Linux": "/mnt/estudio/2027/CINE2/FROM_VFX",
    },
}

_LEGACY = {"hosts": {"ws1": _ROOT_2026["COMP"]}, "default": _ROOT_2026["COMP"]}


@pytest.fixture(autouse=True)
def _restaurar_estado(monkeypatch):
    """Aisla cada test: entorno, ``__main__`` e inyector sin efectos residuales."""
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
    """Modulo nuke fake minimo: GUI + message con grabacion."""

    def __init__(self, gui=True, reads=None):
        self.GUI = gui
        self.messages = []
        self.reads = reads or []

    def message(self, texto):
        self.messages.append(texto)

    def allNodes(self, tipo):
        if tipo == "Read":
            return list(self.reads)
        return []


class _NodoReadFake:
    """Nodo Read fake: el knob file re-evalua ``[getenv X]`` contra os.environ.

    Modela el comportamiento real de Nuke: ``fromScript`` re-evalua los tokens
    TCL ``[getenv ...]`` con el entorno ACTUAL, asi un cambio de env cambia la
    ruta resuelta y el widget debe recargar el nodo.
    """

    def __init__(self, nombre, script, valor):
        self.nombre = nombre
        self._script = script
        self._valor = valor
        self.reloads = 0
        self._tabla = {"file": self, "reload": self}

    def knobs(self):
        return self._tabla

    def __getitem__(self, nombre):
        return self._tabla[nombre]

    def toScript(self):
        return self._script

    def value(self):
        return self._valor

    def fromScript(self, script):
        self._script = script
        self._valor = self._evaluar(script)

    def execute(self):
        self.reloads += 1

    @staticmethod
    def _evaluar(script):
        import re

        def _sust(m):
            return os.environ.get(m.group(1), "")

        return re.sub(r"\[getenv ([A-Za-z_]+)\]", _sust, script)


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


def _items_combo(combo):
    """Items de un QComboBox como lista de strings."""
    return [combo.itemText(i) for i in range(combo.count())]


def _spy_aplicar_env(monkeypatch):
    """Envuelve ``cachear_env``/``aplicar_entorno`` grabando los dicts recibidos.

    Los wrappers delegan en la implementacion real para que ``os.environ`` y
    el cache del injector sigan funcionando.
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
# REQ-1: render de datos del helper + environment intacto + combo presente
# ---------------------------------------------------------------------------


def test_dialogo_conocido_muestra_raiz_estado_y_combo(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    env_antes = dict(os.environ)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS", perfiles=["ana", "pedro"]
    )
    qtbot.addWidget(dialogo)

    assert dialogo.label_perfil.text() == "Raiz actual: /Volumes/estudio/2026/CINE/TO_VFX"
    assert dialogo.label_unidad.text() == "Unidad: Conectado."
    assert _items_combo(dialogo.combo_perfiles) == ["ana", "pedro"]
    assert dialogo.combo_perfiles.currentText() == "ana"
    assert dict(os.environ) == env_antes


def test_dialogo_abrir_y_cancelar_no_muta_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    env_antes = dict(os.environ)

    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS", perfiles=["ana"]
    )
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
# Combo S4: store vacio -> combo vacio + onboarding; refresh en cada open
# ---------------------------------------------------------------------------


def test_combo_vacio_con_store_vacio_muestra_onboarding(qtbot, monkeypatch, tmp_path):
    """Spec S4: store vacio -> combo vacio mas el formulario de onboarding."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {})

    estado = path_manager.estado_panel(ruta, "nuevo", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "nuevo", ruta, "macOS", perfiles=[]
    )
    qtbot.addWidget(dialogo)

    assert dialogo.combo_perfiles.count() == 0
    assert dialogo.label_perfil.text() == "Onboarding: defina la base del proyecto"
    assert dialogo.boton_onboarding is not None


def test_abrir_dialogo_refresca_lista_perfiles_al_abrir(monkeypatch, tmp_path):
    """Spec S4 escenario "open refreshes the profile list".

    ``abrir_dialogo`` relee el store en CADA open: si el store gano un usuario
    entre aperturas, el combo lo lista la siguiente vez.
    """
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    fake = _NukeFake(gui=True)
    construidos = []

    class _Registro:
        def __init__(self, estado, usuario, ruta_store, so, perfiles=None, parent=None, seleccion_path=None):
            construidos.append(list(perfiles or []))
            self._user = usuario

        def exec(self):
            pass

    monkeypatch.setattr(path_manager_panel, "PathManagerDialog", _Registro)
    monkeypatch.setattr(path_manager_panel, "nuke", fake)

    path_manager_panel.abrir_dialogo(
        nuke_mod=fake, usuario="ana", ruta_store=ruta, so="macOS"
    )
    assert construidos == [["ana"]]

    _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    path_manager_panel.abrir_dialogo(
        nuke_mod=fake, usuario="ana", ruta_store=ruta, so="macOS"
    )
    assert construidos == [["ana"], ["ana", "pedro"]]


# ---------------------------------------------------------------------------
# Combo S4: apply-on-select -> env + refresco de Reads
# ---------------------------------------------------------------------------


def test_seleccion_aplica_env_y_refresca_reads(qtbot, monkeypatch, tmp_path):
    """Spec S4 escenario "selecting a profile applies env and refreshes Reads".

    Seleccionar ``pedro`` (raices 2027) aplica su env (PROJECT_ROOT cambia) y
    refresca los Reads: el Read dinamico ``[getenv PROJECT_ROOT]`` recarga por
    cambio de ruta resuelta y el Read estatico NO se toca.
    """
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2027})
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)

    read_getenv = _NodoReadFake(
        "read_getenv",
        "[getenv PROJECT_ROOT]/COMP/plate.%04d.exr",
        "/Volumes/estudio/2026/CINE/TO_VFX/COMP/plate.0001.exr",
    )
    read_estatico = _NodoReadFake(
        "read_estatico",
        "/Volumes/estudio/2026/CINE/STATIC/plate.exr",
        "/Volumes/estudio/2026/CINE/STATIC/plate.exr",
    )
    fake_nuke = _NukeFake(gui=True, reads=[read_getenv, read_estatico])
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS", perfiles=["ana", "pedro"]
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_perfiles.setCurrentIndex(1)  # el artista selecciona "pedro"

    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2027/CINE2/TO_VFX"
    assert aplicados[-1]["PYTHON_COMP"] == "/Volumes/estudio/2027/CINE2/COMP"
    assert cacheados[-1] == aplicados[-1]
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2027/CINE2/TO_VFX"
    assert fake_nuke.messages, "la seleccion informa al artista via nuke.message"
    assert read_getenv.reloads == 1, "el Read dinamico recarga por cambio de ruta"
    assert read_estatico.reloads == 0, "el Read estatico no cambia de ruta: sin reload"


def test_seleccion_stale_valueerror_no_aplica_env_parcial(qtbot, monkeypatch, tmp_path):
    """Spec S4 escenario "stale selection is surfaced without partial env".

    El combo lista ``ana`` (captura del open) pero el store ya no la contiene:
    el ``ValueError`` se informa y NO llega env parcial ni a cache ni a
    ``os.environ``.
    """
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": _ROOT_2026})
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    env_antes = dict(os.environ)

    estado = path_manager.estado_panel(ruta, "pedro", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "pedro", ruta, "macOS", perfiles=["ana", "pedro"]
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_perfiles.setCurrentIndex(0)  # selecciona "ana" (ya no existe)

    assert cacheados == []
    assert aplicados == []
    assert dict(os.environ) == env_antes
    assert fake_nuke.messages, "el ValueError se informa via nuke.message"
    assert "ana" in fake_nuke.messages[-1]


def test_legacy_avisa_regeneracion_y_sigue_onboarding(qtbot, monkeypatch, tmp_path):
    """Spec S4 escenario "legacy store warns before onboarding".

    Una entrada con forma VIEJA (hosts/default) flaggeada por el helper
    dispara el aviso de regeneracion al abrir y el flujo sigue con el
    formulario de onboarding (forma nueva).
    """
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _LEGACY})
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    assert estado["legacy"] is True
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS", perfiles=["ana"]
    )
    qtbot.addWidget(dialogo)

    assert fake_nuke.messages, "el aviso legacy se muestra via nuke.message"
    assert any("regener" in m.lower() for m in fake_nuke.messages)
    assert dialogo.boton_onboarding is not None  # el flujo sigue con onboarding


# ---------------------------------------------------------------------------
# REQ-2: onboarding -> asegurar_perfil una vez + env aplicado (usuario-solo)
# ---------------------------------------------------------------------------


def test_onboarding_submit_asegura_una_vez_y_aplica_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": _ROOT_2026})

    aseguraron = []
    real_asegurar = rutas_engine.asegurar_perfil

    def spy_asegurar(usuario, ruta_store, **kwargs):
        aseguraron.append((usuario, ruta_store, kwargs))
        return real_asegurar(usuario, ruta_store, **kwargs)

    monkeypatch.setattr(rutas_engine, "asegurar_perfil", spy_asegurar)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "nuevo", "macOS")
    assert estado["conocido"] is False
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "nuevo", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=str(tmp_path / "seleccion.json"),
    )
    qtbot.addWidget(dialogo)

    assert dialogo.label_perfil.text() == "Onboarding: defina la base del proyecto"
    assert "nuevo" not in _items_combo(dialogo.combo_perfiles)

    dialogo.campo_base.setText("/Volumes/estudio/2026")
    dialogo.boton_onboarding.click()

    assert len(aseguraron) == 1
    assert aseguraron[0][0] == "nuevo"
    assert aseguraron[0][1] == ruta
    assert aseguraron[0][2]["base"] == "/Volumes/estudio/2026"
    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert cacheados[-1] == aplicados[-1]
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["nuevo"]["COMP"]["macOS"] == "/Volumes/estudio/2026/COMP"


# ---------------------------------------------------------------------------
# REQ-3 (S4): cambio de base por ESPACIO -> slot persistido + env re-aplicado
# ---------------------------------------------------------------------------


def test_cambio_base_por_espacio_persiste_y_aplica_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS", perfiles=["ana"]
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_espacio.setCurrentText("COMP")
    dialogo.campo_base.setText("/Volumes/estudio/2026/CINE2/COMP")
    dialogo.boton_cambio.click()

    # Slot (COMP, macOS) reemplazado; raices de otros espacios/SO intactas.
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE2/COMP"
    assert guardado["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert guardado["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    # El env se re-aplica via injector (PROJECT_ROOT = fallback AD7: primera
    # raiz del SO sin corte ni base).
    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert os.environ["PROJECT_ROOT"] == aplicados[-1]["PROJECT_ROOT"]
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"


# ---------------------------------------------------------------------------
# REQ-5: abrir_dialogo degrade headless
# ---------------------------------------------------------------------------


def test_abrir_dialogo_sin_gui_no_levanta(monkeypatch):
    fake = _NukeFake(gui=False)
    res = path_manager_panel.abrir_dialogo(
        nuke_mod=fake, usuario="ana", ruta_store="x", so="macOS"
    )
    assert res is None
    assert fake.messages == []
    assert "PROJECT_ROOT" not in os.environ


def test_abrir_dialogo_sin_pyside_no_levanta(monkeypatch):
    import builtins
    import importlib
    import sys

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
        nuke_mod=fake, usuario="ana", ruta_store="x", so="macOS"
    )
    assert res is None
    assert fake.messages == []


# ---------------------------------------------------------------------------
# Seleccion por estacion: preseleccion guardada > usuario > primero
# ---------------------------------------------------------------------------


def test_combo_preselecciona_seleccion_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    path_manager.guardar_seleccion(ruta, "pedro", seleccion_path=sel)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    assert dialogo.combo_perfiles.currentText() == "pedro"


def test_combo_preseleccion_guardada_stale_cae_al_usuario(qtbot, monkeypatch, tmp_path):
    """La seleccion guardada apunta a un perfil borrado: cae a la siguiente regla."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    path_manager.guardar_seleccion(ruta, "fantasma", seleccion_path=sel)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    assert dialogo.combo_perfiles.currentText() == "ana"


def test_combo_preselecciona_usuario_si_no_hay_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    assert dialogo.combo_perfiles.currentText() == "ana"


def test_combo_preselecciona_primero_sin_usuario_ni_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "artista", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    assert dialogo.combo_perfiles.currentText() == "ana"


# ---------------------------------------------------------------------------
# Seleccion por estacion: aplicar un perfil guarda la seleccion local
# ---------------------------------------------------------------------------


def test_aplicar_seleccion_guarda_seleccion(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_perfiles.setCurrentIndex(1)  # selecciona "pedro"

    assert path_manager.cargar_seleccion(ruta, seleccion_path=sel) == "pedro"


# ---------------------------------------------------------------------------
# Onboarding con nombre editable (campo pre-llenado con el usuario, editable)
# ---------------------------------------------------------------------------


def test_onboarding_campo_nombre_prellenado_y_editable(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")

    estado = path_manager.estado_panel(ruta, "artista", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    assert dialogo.campo_nombre.text() == "artista"
    dialogo.campo_nombre.setText("artista_color")
    assert dialogo.campo_nombre.text() == "artista_color"


def test_onboarding_nombre_editable_crea_perfil_con_ese_nombre(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "artista", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    dialogo.campo_nombre.setText("artista_color")
    dialogo.campo_base.setText("/Volumes/estudio/2026")
    dialogo.boton_onboarding.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert "artista_color" in guardado
    assert "artista" not in guardado
    assert guardado["artista_color"]["COMP"]["macOS"] == "/Volumes/estudio/2026/COMP"
    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026"
    assert path_manager.cargar_seleccion(ruta, seleccion_path=sel) == "artista_color"
    assert fake_nuke.messages, "el onboarding debe informar via nuke.message"


def test_onboarding_nombre_vacio_no_crea(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "artista", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    dialogo.campo_nombre.setText("   ")
    dialogo.campo_base.setText("/Volumes/estudio/2026")
    dialogo.boton_onboarding.click()

    assert "artista" not in rutas_engine.leer_perfiles(ruta)
    assert fake_nuke.messages, "el nombre vacio se informa"

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado == {"pedro": _ROOT_2026}


# ---------------------------------------------------------------------------
# Renombrar: re-key conservando las 9 raices + combo refrescado
# ---------------------------------------------------------------------------


def test_renombrar_actualiza_combo_y_store(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    monkeypatch.setattr(
        path_manager_panel.QtWidgets.QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("artista", True)),
    )

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_perfiles.setCurrentIndex(0)  # "ana"
    dialogo.boton_renombrar.click()

    assert dialogo.combo_perfiles.currentText() == "artista"
    assert _items_combo(dialogo.combo_perfiles) == ["artista", "pedro"]
    guardado = rutas_engine.leer_perfiles(ruta)
    assert "ana" not in guardado
    assert guardado == {"artista": _ROOT_2026, "pedro": _ROOT_2026}
    assert path_manager.cargar_seleccion(ruta, seleccion_path=sel) == "artista"
    assert fake_nuke.messages, "el rename informa via nuke.message"


def test_renombrar_a_nombre_existente_informa_sin_romper(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    monkeypatch.setattr(
        path_manager_panel.QtWidgets.QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("pedro", True)),
    )

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = path_manager_panel.PathManagerDialog(
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel,
    )
    qtbot.addWidget(dialogo)

    dialogo.combo_perfiles.setCurrentIndex(0)  # "ana"
    dialogo.boton_renombrar.click()

    assert dialogo.combo_perfiles.currentText() == "ana"
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado == {"ana": _ROOT_2026, "pedro": _ROOT_2026}
    assert "Ya existe" in fake_nuke.messages[-1]