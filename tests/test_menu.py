"""
Tests de SamanTools.ui.menu — slice H4 del cambio load-contract (target del bootstrap).

El modulo es el target de ejecucion del bootstrap V2 (``bootstrap/menu.py``
``_cargar_menu_real``): registra los callbacks del injector exactamente una
vez e importa de forma tolerante el shim, y construye el menu minimo
SamanTools. Es la capa ui, asi que importa ``nuke`` a NIVEL DE MODULO
(0% coverage aceptado por diseno, ADR-7): por eso los tests instalan un fake
MINIMO de nuke en ``sys.modules``, LOCAL a este archivo (conftest sigue
intacto), igual que test_shim/test_bootstrap.

Reglas del slice (spec load-ui-menu + ADR-7 + ADR-2/ADR-4/ADR-5):

  - Bootstrap exec: al ejecutar este archivo como hace el bootstrap
    (``exec`` con namespace minimo), los callbacks se registran, el menu
    SamanTools existe y la ejecucion no lanza (el load devuelve True).
  - Callbacks idempotentes: re-ejecutar/instalar dos veces NO registra
    ``addOnScriptLoad``/``addOnScriptSave`` dos veces (el flag vive en el
    injector, que sys.modules cachea entre re-ejecuciones).
  - Flujo de load con fake: perfil resuelto (con onboarding a store ficticio
    si falta) + override manual ``project_directory`` aplicado + env cacheado
    y aplicado; render farm (``PROJECT_ROOT`` pre-existente) gana -> no-op sin
    onboarding.
  - Save: re-afirma SOLO desde la cache en memoria (spy: ``obtener_ruta_store``
    NO se llama en la ruta de guardado; ademas no hay lock/engine).
  - Menu minimo: SamanTools > Configuracion con UN item de informacion de
    version; sin paneles ni PySide; idempotente.
  - Shim import-safe: un shim que falla al importar no rompe callbacks ni menu.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from SamanTools.core import entorno
from SamanTools.core import rutas_engine
from SamanTools.ui import injector

_RAIZ = Path(__file__).resolve().parent.parent
_RUTA_MENU = _RAIZ / "SamanTools" / "ui" / "menu.py"

OVERRIDE = "/Volumes/estudio/2026/OTRO_COMP"
RUTA_COMP = "/Volumes/estudio/2026/CINE/TO_VFX/ep.nk"
FARM_ROOT = "/mnt/estudio/2026/CINE"

# ---------------------------------------------------------------------------
# Fakes locales al test file (prohibido en conftest por spec load-ui-menu)
# ---------------------------------------------------------------------------


class _KnobFake:
    """Knob fake minimo: value() (duck typing Nuke)."""

    def __init__(self, valor):
        self._valor = valor

    def value(self):
        return self._valor


class _RootFake:
    """Root fake: name() + knobs() con el knob ``project_directory`` opcional."""

    def __init__(self, nombre_script="", project_directory=None):
        self._nombre = nombre_script
        self._knobs = {}
        if project_directory is not None:
            self._knobs["project_directory"] = _KnobFake(project_directory)

    def name(self):
        return self._nombre

    def knobs(self):
        return self._knobs


class _MenuFake:
    """Menu fake minimo: findItem/addMenu/addCommand (duck typing Nuke)."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.submenus = {}
        self.commands = {}

    def findItem(self, nombre):
        if nombre in self.submenus:
            return self.submenus[nombre]
        return self.commands.get(nombre)

    def addMenu(self, nombre):
        if nombre not in self.submenus:
            self.submenus[nombre] = _MenuFake(nombre)
        return self.submenus[nombre]

    def addCommand(self, nombre, comando, shortcut=None):
        if nombre not in self.commands:
            self.commands[nombre] = {"comando": comando, "veces": 0, "shortcut": shortcut}
        self.commands[nombre]["veces"] += 1


class _NukeFake:
    """Nuke fake de modulo (sys.modules, local al test): superficie MINIMA.

    Solo expone menu/addOnScriptLoad/addOnScriptSave/root/message: si el menu
    real intentara paneles, PySide o cualquier otra API, el fake levantaria
    AttributeError y el test fallaria.
    """

    def __init__(self, root=None):
        self._root = root if root is not None else _RootFake()
        self._menus = {"Nuke": _MenuFake("Nuke")}
        self.callbacks = {}
        self.registros = {"load": 0, "save": 0}
        self.mensajes = []

    def addOnScriptLoad(self, callback):
        self.registros["load"] += 1
        self.callbacks["load"] = callback

    def addOnScriptSave(self, callback):
        self.registros["save"] += 1
        self.callbacks["save"] = callback

    def root(self):
        return self._root

    def menu(self, nombre):
        if nombre not in self._menus:
            self._menus[nombre] = _MenuFake(nombre)
        return self._menus[nombre]

    def message(self, texto):
        self.mensajes.append(texto)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fake_nuke(monkeypatch):
    """Aisla cada test: fake nuke en sys.modules, estado del injector, entorno."""
    import __main__

    injector._env_cache = None
    injector._env_inyectado = False
    injector._callbacks_registrados = False
    _expulsar_modulo_menu()

    fake = _NukeFake()
    monkeypatch.setitem(sys.modules, "nuke", fake)
    monkeypatch.delenv("NUKE_PROFILES_PATH", raising=False)
    # S2/AD5: por defecto el probe del store de proyecto responde negativo —
    # la raiz ficticia del plato no tiene .saman/ y la cadena cae al env/config.
    monkeypatch.setattr(injector, "_probe_store", lambda ruta: False)

    env_antes = dict(os.environ)
    main_antes = {k: v for k, v in vars(__main__).items() if k.isupper()}
    yield fake

    for clave in set(os.environ) - set(env_antes):
        del os.environ[clave]
    for clave, valor in env_antes.items():
        os.environ[clave] = valor
    for clave, valor in main_antes.items():
        setattr(__main__, clave, valor)
    for clave in set(vars(__main__)) - set(main_antes):
        if clave.isupper():
            delattr(__main__, clave)
    injector._env_cache = None
    injector._env_inyectado = False
    injector._callbacks_registrados = False
    _expulsar_modulo_menu()


def _expulsar_modulo_menu():
    """Expulsa el modulo menu de sys.modules Y el atributo del paquete padre.

    ``from SamanTools.ui import menu`` resuelve primero el atributo ``menu``
    del paquete ``SamanTools.ui`` (que persiste en sys.modules entre tests):
    si no se limpia, el import devuelve el modulo STALE del test anterior sin
    re-ejecutar su codigo. Limpiar ambos garantiza un import fresco por test.
    """
    sys.modules.pop("SamanTools.ui.menu", None)
    paquete_ui = sys.modules.get("SamanTools.ui")
    if paquete_ui is not None:
        paquete_ui.__dict__.pop("menu", None)


@pytest.fixture
def menu_mod(fake_nuke):
    """Importa el modulo bajo prueba con el fake ya instalado en sys.modules."""
    from SamanTools.ui import menu

    return menu


def _ejecutar_como_bootstrap():
    """Exec del source real como hace bootstrap/menu.py ``_cargar_menu_real``.

    El namespace minimo (__file__/__name__) replica el contrato del bootstrap:
    sin ``__package__``, obligando a imports absolutos y a auto-anadir la raiz
    del checkout a sys.path.
    """
    codigo = _RUTA_MENU.read_text(encoding="utf-8")
    namespace = {"__file__": str(_RUTA_MENU), "__name__": "__saman_menu__"}
    exec(compile(codigo, str(_RUTA_MENU), "exec"), namespace)
    return namespace


def _store_ficticio(tmp_path, monkeypatch):
    """Apunta NUKE_PROFILES_PATH a un store json ficticio (onboarding ahi)."""
    ruta = tmp_path / "nuke_profiles.json"
    monkeypatch.setenv("NUKE_PROFILES_PATH", str(ruta))
    return ruta


# ---------------------------------------------------------------------------
# H4.1: bootstrap exec True, callbacks una vez, menu existe
# ---------------------------------------------------------------------------


def test_bootstrap_exec_registra_callbacks_y_construye_menu(fake_nuke):
    """Spec load-ui-menu 'bootstrap exec path': exec como el bootstrap -> True.

    Los callbacks quedan registrados, el menu SamanTools > Configuracion
    existe con el item de informacion, y la ejecucion no lanza (el load del
    bootstrap devuelve True).
    """
    _ejecutar_como_bootstrap()

    assert fake_nuke.registros["load"] == 1
    assert fake_nuke.registros["save"] == 1

    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    assert saman is not None
    configuracion = saman.findItem("Configuración")
    assert configuracion is not None
    assert configuracion.commands["Información de SamanTools..."]["veces"] == 1


def test_reejecucion_no_duplica_callbacks(fake_nuke):
    """Spec 're-exec does not duplicate': dos execs -> un registro por callback.

    El flag de idempotencia vive en el injector (sys.modules lo cachea entre
    re-ejecuciones aunque cada exec reciba un namespace fresco).
    """
    _ejecutar_como_bootstrap()
    _ejecutar_como_bootstrap()

    assert fake_nuke.registros["load"] == 1
    assert fake_nuke.registros["save"] == 1


def test_instalar_repetido_no_duplica_items(menu_mod, fake_nuke):
    """'instalar()' dos veces no duplica items del menu ni callbacks."""
    assert menu_mod.instalar() is True

    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    configuracion = saman.findItem("Configuración")
    assert configuracion.commands["Información de SamanTools..."]["veces"] == 1
    assert fake_nuke.registros["load"] == 1
    assert fake_nuke.registros["save"] == 1


# ---------------------------------------------------------------------------
# H4.1: flujo de load con fake (perfil + override + env aplicado)
# ---------------------------------------------------------------------------


def test_flujo_load_perfil_override_y_env_aplicados(menu_mod, fake_nuke, tmp_path, monkeypatch):
    """Load completo: perfil (onboarding a store ficticio) + override manual.

    El override ``project_directory`` fuerza PROJECT_ROOT via la cadena de
    precedencia (S2: el corte del plato manda en ``armar_estado_env`` y el
    override se aplica DESPUES sobre el dict final); las PYTHON_* son las
    raices del perfil para el SO explicito (spec S2). El env se cachea y se
    aplica.
    """
    fake_nuke._root = _RootFake(RUTA_COMP, project_directory=OVERRIDE)
    _store_ficticio(tmp_path, monkeypatch)
    monkeypatch.setattr(menu_mod, "_identidad_ambiental", lambda: ("artista_dev", "devhost"))

    fake_nuke.callbacks["load"]()

    assert os.environ["PROJECT_ROOT"] == OVERRIDE
    assert os.environ["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert os.environ["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"
    assert os.environ["PYTHON_FROM_VFX"] == "/Volumes/estudio/2026/CINE/FROM_VFX"
    assert injector._env_inyectado is True
    assert injector._env_cache["PROJECT_ROOT"] == OVERRIDE


def test_flujo_load_sin_override_usa_perfil(menu_mod, fake_nuke, tmp_path, monkeypatch):
    """Sin override declarado, el corte del plato y las raices del perfil mandan."""
    fake_nuke._root = _RootFake(RUTA_COMP)
    _store_ficticio(tmp_path, monkeypatch)
    monkeypatch.setattr(menu_mod, "_identidad_ambiental", lambda: ("artista_dev", "devhost"))

    fake_nuke.callbacks["load"]()

    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert os.environ["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert injector._env_cache["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"


def test_flujo_load_usa_store_del_proyecto(menu_mod, fake_nuke, tmp_path, monkeypatch):
    """S2/AD5: el call-site pasa la raiz del proyecto a ``obtener_ruta_store``.

    ``_resolver_contexto_carga`` calcula ``raiz_proyecto`` desde
    ``nuke.root().name()`` (corte estructural) y la inyecta: con
    ``.saman/nuke_profiles.json`` presente, el perfil se resuelve en el store
    DEL PROYECTO (spy de ``resolver_perfil`` captura la ruta) y el env sale
    del corte del plato.
    """
    raiz = tmp_path / "CINE"
    store = raiz / ".saman" / "nuke_profiles.json"
    perfil = {
        espacio: {so: str(raiz / espacio) for so in ("macOS", "Windows", "Linux")}
        for espacio in ("TO_VFX", "COMP", "FROM_VFX")
    }
    store.parent.mkdir(parents=True)
    store.write_text(json.dumps({"perfiles": {"artista_dev": perfil}}), encoding="utf-8")
    fake_nuke._root = _RootFake(str(raiz / "COMP" / "ep.nk"))
    monkeypatch.setattr(menu_mod, "_identidad_ambiental", lambda: ("artista_dev", "devhost"))
    # Probe REAL sobre tmp_path (filesystem vivo): demuestra la cadena completa.
    monkeypatch.setattr(injector, "_probe_store", lambda ruta: os.path.isfile(ruta))

    capturas = {}

    def espia_resolver(usuario, ruta):
        capturas["ruta"] = ruta
        return perfil

    monkeypatch.setattr(rutas_engine, "resolver_perfil", espia_resolver)

    fake_nuke.callbacks["load"]()

    assert capturas["ruta"] == str(store)
    assert os.environ["PROJECT_ROOT"] == str(raiz)
    assert os.environ["PYTHON_COMP"] == str(raiz / "COMP")
    assert injector._env_cache["PROJECT_ROOT"] == str(raiz)


def test_flujo_load_untitled_cae_a_env_y_fallback_so(menu_mod, fake_nuke, tmp_path, monkeypatch):
    """S2: script untitled (sin raiz de proyecto) -> cadena al env; env con la
    root del perfil para el SO explicito (fallback AD7, sin corte ni base)."""
    fake_nuke._root = _RootFake("")
    _store_ficticio(tmp_path, monkeypatch)
    monkeypatch.setattr(menu_mod, "_identidad_ambiental", lambda: ("artista_dev", "devhost"))
    monkeypatch.setattr(entorno, "detectar_so", lambda: "macOS")

    fake_nuke.callbacks["load"]()

    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert os.environ["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert injector._env_inyectado is True


def test_flujo_load_env_preexistente_gana_no_op(menu_mod, fake_nuke, monkeypatch):
    """ADR-4: PROJECT_ROOT pre-existente (render farm) -> no-op sin onboarding."""
    os.environ["PROJECT_ROOT"] = FARM_ROOT
    resoluciones = {"n": 0}
    original = rutas_engine.resolver_perfil

    def espia(usuario, ruta):
        resoluciones["n"] += 1
        return original(usuario, ruta)

    monkeypatch.setattr(rutas_engine, "resolver_perfil", espia)

    fake_nuke.callbacks["load"]()

    assert os.environ["PROJECT_ROOT"] == FARM_ROOT
    assert resoluciones["n"] == 0
    assert injector._env_inyectado is False
    assert injector._env_cache is None


# ---------------------------------------------------------------------------
# H4.1: save re-assert SOLO desde memoria (sin store, sin lock)
# ---------------------------------------------------------------------------


def test_save_rea_afirma_desde_memoria_sin_store(menu_mod, fake_nuke, tmp_path, monkeypatch):
    """ADR-2: el save re-aplica la cache en memoria y NO toca el store.

    Se elimina PROJECT_ROOT del entorno (como si un knobChanged la pisara
    durante la sesion) y el save la restaura desde la cache; el spy de
    ``obtener_ruta_store`` demuestra que la ruta de guardado nunca consulta
    disco.
    """
    fake_nuke._root = _RootFake(RUTA_COMP)
    _store_ficticio(tmp_path, monkeypatch)
    monkeypatch.setattr(menu_mod, "_identidad_ambiental", lambda: ("artista_dev", "devhost"))

    fake_nuke.callbacks["load"]()
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"

    llamadas_store = {"n": 0}
    original_store = injector.obtener_ruta_store

    def spy_store(*_args, **_kwargs):
        llamadas_store["n"] += 1
        return original_store(*_args, **_kwargs)

    monkeypatch.setattr(injector, "obtener_ruta_store", spy_store)

    os.environ.pop("PROJECT_ROOT", None)
    fake_nuke.callbacks["save"]()

    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert llamadas_store["n"] == 0


def test_save_sin_cache_no_escribe_nada(menu_mod, fake_nuke, monkeypatch):
    """Sin flujo de load previo, el save no escribe nada (memoria vacia)."""
    env_antes = dict(os.environ)
    fake_nuke.callbacks["save"]()
    assert dict(os.environ) == env_antes


# ---------------------------------------------------------------------------
# H4.1: shim import-safe (fallo tolerado) + menu minimo sin PySide/paneles
# ---------------------------------------------------------------------------


def test_shim_import_fallido_no_rompe_callbacks_ni_menu(fake_nuke, monkeypatch):
    """Spec 'shim import failure tolerated': rutas roto -> callbacks y menu OK."""
    monkeypatch.setitem(sys.modules, "SamanTools.rutas", None)

    _ejecutar_como_bootstrap()

    assert fake_nuke.registros["load"] == 1
    assert fake_nuke.registros["save"] == 1
    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    assert saman.findItem("Configuración").findItem("Información de SamanTools...") is not None


def test_sin_pyside_ni_creacion_de_paneles():
    """Spec 'minimal menu without panels': sin PySide ni nodePaste en el source."""
    fuente = _RUTA_MENU.read_text(encoding="utf-8")
    assert re.search(r"^\s*(?:import\s+PySide|from\s+PySide)", fuente, re.M) is None
    assert "nodePaste" not in fuente
    assert "addPanel" not in fuente


def test_importa_nuke_a_nivel_de_modulo():
    """Decision ADR-7: la capa ui importa nuke al tope (0% coverage por diseno)."""
    fuente = _RUTA_MENU.read_text(encoding="utf-8")
    assert re.search(r"^import\s+nuke\b", fuente, re.M) is not None


# ---------------------------------------------------------------------------
# H4.1: item de informacion de version (menú mínimo)
# ---------------------------------------------------------------------------


def test_item_version_anuncia_version_del_paquete(menu_mod, fake_nuke):
    """El item de informacion muestra la version SemVer del paquete."""
    menu_mod._mostrar_info_version()
    assert fake_nuke.mensajes
    ultimo = fake_nuke.mensajes[-1]
    assert "SamanTools V2" in ultimo
    assert "2.0.0" in ultimo


# ---------------------------------------------------------------------------
# P3 (3.1): item Path Manager en el menu SamanTools (REQ-1/REQ-2/REQ-3, D1/D5)
# ---------------------------------------------------------------------------
# REQ-1: registra el item, idempotente, sin abrir dialogo al instalar.
# REQ-2: nunca importa PySide a nivel de modulo (guard regex + sys.modules).
# REQ-3: colision del atajo -> fallback Ctrl+Alt+O sin romper el build (D5).


def test_instalar_registra_item_path_manager_sin_duplicar(menu_mod, fake_nuke):
    """REQ-1: dos installs -> UN item "Path Manager..." con Ctrl+Alt+R."""
    assert menu_mod.instalar() is True
    menu_mod.instalar()

    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    item = saman.commands["Path Manager..."]
    assert item["veces"] == 1
    assert item["shortcut"] == menu_mod._ATAJO_PATH_MANAGER
    assert item["shortcut"] == "Ctrl+Alt+R"


def test_instalar_no_abre_dialogo_ni_importa_pyside(fake_nuke):
    """REQ-1/REQ-2: instalar dos veces no abre dialogo ni trae PySide."""
    antes = {k for k in sys.modules if k.startswith("PySide")}
    _ejecutar_como_bootstrap()
    _ejecutar_como_bootstrap()
    despues = {k for k in sys.modules if k.startswith("PySide")}

    assert despues == antes
    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    assert saman.commands["Path Manager..."]["veces"] == 1


def test_click_path_manager_importa_panel_y_abre_dialogo(menu_mod, fake_nuke, monkeypatch):
    """REQ-2: el click importa el panel recien ahi y abre el dialogo (fake)."""
    abiertos = {"n": 0}

    class _PanelFake:
        @staticmethod
        def abrir_dialogo(*args, **kwargs):
            abiertos["n"] += 1

    paquete_ui = sys.modules.get("SamanTools.ui")
    if paquete_ui is not None:
        monkeypatch.setattr(paquete_ui, "path_manager_panel", _PanelFake, raising=False)
    monkeypatch.setitem(sys.modules, "SamanTools.ui.path_manager_panel", _PanelFake)

    menu_mod.instalar()
    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    comando = saman.commands["Path Manager..."]["comando"]

    comando()  # el "click" del usuario en el menu

    assert abiertos["n"] == 1


def test_colision_atajo_usa_fallback_ctrl_alt_o(menu_mod, fake_nuke, monkeypatch):
    """REQ-3: "Ctrl+Alt+R" ocupado -> el item usa el fallback y el menu sigue.

    El import del modulo ya registro el item con el predicado real (optimista):
    se simula la colision expulsando ese registro (sin item previo en la
    sesion) y re-ejecutando el build con el predicado inyectado — patcheado a
    True para el atajo principal (D5).
    """
    monkeypatch.setattr(
        menu_mod, "_atajo_ocupado", lambda atajo: atajo == "Ctrl+Alt+R"
    )
    saman = fake_nuke._menus["Nuke"].findItem("SamanTools")
    del saman.commands["Path Manager..."]  # sesion sin registro previo del item

    assert menu_mod.instalar() is True

    item = saman.commands["Path Manager..."]
    assert item["shortcut"] == menu_mod._ATAJO_FALLBACK_PATH_MANAGER
    assert item["shortcut"] == "Ctrl+Alt+O"


def test_seleccionar_atajo_mantiene_principal_si_libre(menu_mod):
    """D5: predicado False -> se mantiene el atajo principal."""
    assert (
        menu_mod.seleccionar_atajo("Ctrl+Alt+R", "Ctrl+Alt+O", lambda a: False)
        == "Ctrl+Alt+R"
    )


def test_seleccionar_atajo_degrade_al_fallback_si_ocupado(menu_mod):
    """D5: predicado True -> triangulacion: degrada al fallback."""
    assert (
        menu_mod.seleccionar_atajo("Ctrl+Alt+R", "Ctrl+Alt+O", lambda a: True)
        == "Ctrl+Alt+O"
    )