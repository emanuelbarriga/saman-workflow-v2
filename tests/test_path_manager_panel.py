"""Tests del dialogo Path Manager — rediseno UX segun mockup (modos normal /
onboarding / avanzado, opcion A: combo apply-on-select + Guardar y Aplicar).

Cubre el widget ``SamanTools/ui/path_manager_panel.py`` (TDD estricto,
pytest-qt) sobre el contrato usuario-solo de perfil-por-usuario (AD2): el
dialogo consume DATOS del helper (estado, semaforo via ``estado_unidad``,
LISTA de perfiles) y NUNCA computa perfiles ni escribe el entorno por su
cuenta (el env solo viaja por ``injector.cachear_env`` + ``aplicar_entorno``).

* Modo normal (mockup): combo de perfiles (apply-on-select NO espera al boton),
  semaforo del disco (verde OK / rojo ERROR), campo 'Ruta Base del Proyecto'
  con 'Buscar carpeta...', checkbox avanzado (desmarcado por defecto) que
  alterna modo simple (UNA base -> los TRES espacios del SO actual) y modo
  avanzado (COMP / FROM_VFX / TO_VFX con rutas actuales, 'Buscar...' y
  semaforo propio). Botones: Renombrar Perfil, Guardar y Aplicar, Cerrar.
* Modo onboarding (mockup): banner informativo, campo 'Nombre del Perfil'
  editable, 'Ruta Base de Trabajo' + 'Buscar...', semaforo del montaje y
  boton 'Crear Perfil y Vincular' (nunca 'Onboarding'), sin checkbox avanzado.
* Semáforo: ``_texto_semaforo``/``_hoja_semaforo`` puros (verde/rojo) y
  ``entorno.estado_unidad`` del motor (timeout + cache ~10s).
* Buscar carpeta: ``QFileDialog.getExistingDirectory`` mockeado; cancelar no
  toca el campo.
* Se mantienen: preseleccion por estacion (S5), renombrar, onboarding con
  nombre editable, degrade headless y refresco de Reads al aplicar.

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
    inj_antes = (injector._env_cache, injector._env_inyectado)
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
    injector._env_cache, injector._env_inyectado = inj_antes


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


def _marcar_desconectado(base):
    return {"conectado": False, "ruta": None, "detalle": "Mount colgado (timeout 3s)."}


def _items_combo(combo):
    """Items de un QComboBox como lista de strings."""
    return [combo.itemText(i) for i in range(combo.count())]


def _construir_dialogo(dialogo_cls, estado, usuario, ruta, so, perfiles=None, seleccion_path=None, qtbot=None):
    """Construye el dialogo y (si hay qtbot) lo registra para el cleanup."""
    d = dialogo_cls(
        estado, usuario, ruta, so,
        perfiles=perfiles, seleccion_path=seleccion_path,
    )
    if qtbot is not None:
        qtbot.addWidget(d)
    return d


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
# Modo normal: render de datos del helper + environment intacto
# ---------------------------------------------------------------------------


def test_dialogo_conocido_renderiza_estado_combo_semaforo_y_botones(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    env_antes = dict(os.environ)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], qtbot=qtbot,
    )

    assert dialogo.windowTitle() == "Path Manager — Nuke"
    assert _items_combo(dialogo.combo_perfiles) == ["ana", "pedro"]
    assert dialogo.combo_perfiles.currentText() == "ana"
    assert dialogo.campo_base.text() == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert dialogo.semaforo_base.text() == "OK — Conectado — /Volumes/estudio/2026/CINE/TO_VFX"
    assert dialogo.boton_guardar.text() == "Guardar y Aplicar"
    assert dialogo.boton_renombrar.text() == "Renombrar Perfil"
    assert dialogo.boton_cerrar.text() == "Cerrar"
    assert dialogo.checkbox_avanzado.isChecked() is False
    assert dict(os.environ) == env_antes


def test_dialogo_simple_muestra_solo_campo_base_y_avanzado_oculto(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    assert dialogo.contenedor_simple.isHidden() is False
    assert dialogo.grupo_avanzado.isHidden() is True


def test_dialogo_abrir_y_cancelar_no_muta_env(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )
    env_antes = dict(os.environ)

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
# Semáforo: texto y estilo puros + error mostrado en rojo
# ---------------------------------------------------------------------------


def test_texto_semaforo_ok_y_error():
    ok = {"conectado": True, "ruta": "/Volumes/estudio/2026/CINE/TO_VFX", "detalle": "Conectado."}
    assert (
        path_manager_panel._texto_semaforo(ok)
        == "OK — Conectado — /Volumes/estudio/2026/CINE/TO_VFX"
    )
    err = {"conectado": False, "ruta": None, "detalle": "Mount colgado (timeout 3s)."}
    assert (
        path_manager_panel._texto_semaforo(err)
        == "ERROR — Desconectado — Mount colgado (timeout 3s)."
    )
    assert path_manager_panel._hoja_semaforo(ok) == path_manager_panel._ESTILO_OK
    assert path_manager_panel._hoja_semaforo(err) == path_manager_panel._ESTILO_ERROR


def test_semaforo_error_rojo_muestra_detalle(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_desconectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    assert dialogo.semaforo_base.text() == "ERROR — Desconectado — Mount colgado (timeout 3s)."
    assert path_manager_panel._ESTILO_ERROR in dialogo.semaforo_base.styleSheet()


# ---------------------------------------------------------------------------
# Combo S4: store vacio -> onboarding; refresh en cada open
# ---------------------------------------------------------------------------


def test_combo_vacio_con_store_vacio_muestra_onboarding(qtbot, monkeypatch, tmp_path):
    """Spec S4: store vacio -> onboarding (banner + 'Crear Perfil y Vincular')."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {})

    estado = path_manager.estado_panel(ruta, "nuevo", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "nuevo", ruta, "macOS",
        perfiles=[], qtbot=qtbot,
    )

    assert dialogo.windowTitle() == "Path Manager — Bienvenido"
    assert not hasattr(dialogo, "combo_perfiles")  # sin combo en onboarding
    assert getattr(dialogo, "checkbox_avanzado", None) is None  # primera vez = simple
    assert dialogo.banner is not None
    assert "perfil asignado" in dialogo.banner.text()
    assert dialogo.boton_onboarding.text() == "Crear Perfil y Vincular"
    visibles = (dialogo.banner.text(), dialogo.boton_onboarding.text())
    assert not any("Onboarding" in t for t in visibles)


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
# Combo S4: apply-on-select -> env + refresco de Reads (sin boton)
# ---------------------------------------------------------------------------


def test_seleccion_aplica_env_y_refresca_reads(qtbot, monkeypatch, tmp_path):
    """Spec S4 escenario "selecting a profile applies env and refreshes Reads".

    Seleccionar ``pedro`` (raices 2027) aplica su env (PROJECT_ROOT cambia) y
    refresca los Reads: el Read dinamico ``[getenv PROJECT_ROOT]`` recarga por
    cambio de ruta resuelta y el Read estatico NO se toca. LA SELECCION NO
    ESPERA a 'Guardar y Aplicar'.
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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], qtbot=qtbot,
    )

    dialogo.combo_perfiles.setCurrentIndex(1)  # el artista selecciona "pedro"

    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2027/CINE2/TO_VFX"
    assert aplicados[-1]["PYTHON_COMP"] == "/Volumes/estudio/2027/CINE2/COMP"
    assert cacheados[-1] == aplicados[-1]
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2027/CINE2/TO_VFX"
    assert fake_nuke.messages, "la seleccion informa al artista via nuke.message"
    assert read_getenv.reloads == 1, "el Read dinamico recarga por cambio de ruta"
    assert read_estatico.reloads == 0, "el Read estatico no cambia de ruta: sin reload"
    # La seleccion sincroniza el campo base con el perfil activo (mockup).
    assert dialogo.campo_base.text() == "/Volumes/estudio/2027/CINE2/TO_VFX"


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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "pedro", ruta, "macOS",
        perfiles=["ana", "pedro"], qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    assert fake_nuke.messages, "el aviso legacy se muestra via nuke.message"
    assert any("regener" in m.lower() for m in fake_nuke.messages)
    assert dialogo.boton_onboarding is not None  # el flujo sigue con onboarding


# ---------------------------------------------------------------------------
# Modo avanzado: checkbox muestra 3 campos con rutas actuales del perfil
# ---------------------------------------------------------------------------


def test_checkbox_avanzado_alterna_campos(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    assert dialogo.checkbox_avanzado.isChecked() is False
    assert dialogo.grupo_avanzado.isHidden() is True
    assert dialogo.contenedor_simple.isHidden() is False

    dialogo.checkbox_avanzado.setChecked(True)
    assert dialogo.grupo_avanzado.isHidden() is False
    assert dialogo.contenedor_simple.isHidden() is True

    dialogo.checkbox_avanzado.setChecked(False)
    assert dialogo.grupo_avanzado.isHidden() is True
    assert dialogo.contenedor_simple.isHidden() is False


def test_modo_avanzado_muestra_tres_campos_con_rutas_actuales(qtbot, monkeypatch, tmp_path):
    """Mockup: modo avanzado = 3 campos simultaneos (COMP, FROM_VFX, TO_VFX)
    en el orden del usuario, con las rutas actuales del perfil para el SO."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.checkbox_avanzado.setChecked(True)
    assert list(dialogo.campos_avanzados) == ["COMP", "FROM_VFX", "TO_VFX"]
    assert dialogo.campos_avanzados["COMP"].text() == "/Volumes/estudio/2026/CINE/COMP"
    assert dialogo.campos_avanzados["FROM_VFX"].text() == "/Volumes/estudio/2026/CINE/FROM_VFX"
    assert dialogo.campos_avanzados["TO_VFX"].text() == "/Volumes/estudio/2026/CINE/TO_VFX"
    for espacio in ("COMP", "FROM_VFX", "TO_VFX"):
        assert dialogo.botones_buscar_avanzados[espacio].text() == "Buscar..."
        assert dialogo.semaforos_avanzados[espacio].text().startswith("OK")


def test_semaforo_avanzado_por_espacio(qtbot, monkeypatch, tmp_path):
    """Cada campo avanzado tiene su semaforo: COMP desconectado, otros OK."""
    monkeypatch.setattr(
        entorno,
        "estado_unidad",
        lambda b: _marcar_desconectado(b)
        if b == "/Volumes/estudio/2026/CINE/COMP"
        else _marcar_conectado(b),
    )
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.checkbox_avanzado.setChecked(True)
    assert dialogo.semaforos_avanzados["COMP"].text().startswith("ERROR")
    assert "Mount colgado" in dialogo.semaforos_avanzados["COMP"].text()
    assert dialogo.semaforos_avanzados["FROM_VFX"].text().startswith("OK")
    assert dialogo.semaforos_avanzados["TO_VFX"].text().startswith("OK")


# ---------------------------------------------------------------------------
# Guardar y Aplicar (opcion A): simple -> 3 espacios; avanzado -> por espacio
# ---------------------------------------------------------------------------


def test_guardar_aplicar_simple_escribe_tres_espacios(qtbot, monkeypatch, tmp_path):
    """Modo simple (checkbox desmarcado): la base del campo se escribe en los
    TRES espacios del SO actual (modo TODOS via guardar_base_unificada)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.campo_base.setText("/Volumes/estudio/2027")
    dialogo.boton_guardar.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2027/COMP"
    assert guardado["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2027/TO_VFX"
    assert guardado["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2027/FROM_VFX"
    assert guardado["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert aplicados[-1]["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert os.environ["PROJECT_ROOT"] == "/Volumes/estudio/2027"
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"


def test_guardar_aplicar_simple_sin_base_informa_sin_guardar(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.campo_base.setText("   ")
    dialogo.boton_guardar.click()

    assert rutas_engine.leer_perfiles(ruta) == {"ana": _ROOT_2026}
    assert fake_nuke.messages and "base" in fake_nuke.messages[-1].lower()


def test_guardar_aplicar_avanzado_escribe_por_espacio(qtbot, monkeypatch, tmp_path):
    """Modo avanzado: cada campo editado escribe SOLO su espacio (per-space);
    TO_VFX sin cambios queda intacto y otros SO intactos."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )
    dialogo.checkbox_avanzado.setChecked(True)

    dialogo.campos_avanzados["COMP"].setText("/Volumes/estudio/2027/CINE2/COMP")
    dialogo.campos_avanzados["FROM_VFX"].setText("/Volumes/estudio/2027/CINE2/FROM_VFX")
    dialogo.boton_guardar.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["COMP"]["macOS"] == "/Volumes/estudio/2027/CINE2/COMP"
    assert guardado["ana"]["FROM_VFX"]["macOS"] == "/Volumes/estudio/2027/CINE2/FROM_VFX"
    assert guardado["ana"]["TO_VFX"]["macOS"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert guardado["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert aplicados[-1]["PYTHON_COMP"] == "/Volumes/estudio/2027/CINE2/COMP"
    assert aplicados[-1]["PYTHON_FROM_VFX"] == "/Volumes/estudio/2027/CINE2/FROM_VFX"
    assert fake_nuke.messages, "el submit debe informar al artista via nuke.message"


def test_guardar_avanzado_campo_vacio_informa_sin_guardar(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )
    dialogo.checkbox_avanzado.setChecked(True)

    dialogo.campos_avanzados["COMP"].setText("   ")
    dialogo.boton_guardar.click()

    assert rutas_engine.leer_perfiles(ruta) == {"ana": _ROOT_2026}
    assert fake_nuke.messages and "COMP" in fake_nuke.messages[-1]


# ---------------------------------------------------------------------------
# Buscar carpeta (QFileDialog.getExistingDirectory)
# ---------------------------------------------------------------------------


def test_buscar_carpeta_rellena_campo_base(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    monkeypatch.setattr(
        path_manager_panel.QtWidgets.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda parent, titulo, ruta_inicial: "/Volumes/estudio/2027"),
    )

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.boton_buscar_base.click()
    assert dialogo.campo_base.text() == "/Volumes/estudio/2027"


def test_buscar_carpeta_rellena_campo_avanzado(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    monkeypatch.setattr(
        path_manager_panel.QtWidgets.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda parent, titulo, ruta_inicial: "/Volumes/estudio/2027/CINE2/COMP"),
    )

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )
    dialogo.checkbox_avanzado.setChecked(True)

    dialogo.botones_buscar_avanzados["COMP"].click()
    assert dialogo.campos_avanzados["COMP"].text() == "/Volumes/estudio/2027/CINE2/COMP"


def test_buscar_carpeta_cancelar_no_toca_campo(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026})
    monkeypatch.setattr(
        path_manager_panel.QtWidgets.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda parent, titulo, ruta_inicial: ""),
    )

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana"], qtbot=qtbot,
    )

    dialogo.boton_buscar_base.click()
    assert dialogo.campo_base.text() == "/Volumes/estudio/2026/CINE/TO_VFX"


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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "nuevo", ruta, "macOS",
        perfiles=["pedro"], qtbot=qtbot,
    )

    assert dialogo.banner is not None
    assert "nuevo" not in rutas_engine.leer_perfiles(ruta)

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
# Seleccion por estacion: preseleccion guardada > usuario > primero
# ---------------------------------------------------------------------------


def test_combo_preselecciona_seleccion_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    path_manager.guardar_seleccion(ruta, "pedro", seleccion_path=sel)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

    assert dialogo.combo_perfiles.currentText() == "pedro"


def test_combo_preseleccion_guardada_stale_cae_al_usuario(qtbot, monkeypatch, tmp_path):
    """La seleccion guardada apunta a un perfil borrado: cae a la siguiente regla."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")
    path_manager.guardar_seleccion(ruta, "fantasma", seleccion_path=sel)

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

    assert dialogo.combo_perfiles.currentText() == "ana"


def test_combo_preselecciona_usuario_si_no_hay_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

    assert dialogo.combo_perfiles.currentText() == "ana"


def test_combo_preselecciona_primero_sin_usuario_ni_guardada(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    ruta = _escribir_store(tmp_path, {"ana": _ROOT_2026, "pedro": _ROOT_2026})
    sel = str(tmp_path / "seleccion.json")

    estado = path_manager.estado_panel(ruta, "ana", "macOS")
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "artista", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel, qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel, qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "artista", ruta, "macOS",
        perfiles=["pedro"], seleccion_path=sel, qtbot=qtbot,
    )

    dialogo.campo_nombre.setText("   ")
    dialogo.campo_base.setText("/Volumes/estudio/2026")
    dialogo.boton_onboarding.click()

    assert rutas_engine.leer_perfiles(ruta) == {"pedro": _ROOT_2026}
    assert fake_nuke.messages, "el nombre vacio se informa"


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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

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
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, "ana", ruta, "macOS",
        perfiles=["ana", "pedro"], seleccion_path=sel, qtbot=qtbot,
    )

    dialogo.combo_perfiles.setCurrentIndex(0)  # "ana"
    dialogo.boton_renombrar.click()

    assert dialogo.combo_perfiles.currentText() == "ana"
    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado == {"ana": _ROOT_2026, "pedro": _ROOT_2026}
    assert "Ya existe" in fake_nuke.messages[-1]


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
# Espacios EXTRA (PR 4, spec panel-path-manager-widget): subarbol separado,
# filas con nombre+ruta+semaforo, OS por fila (D2), add/OK/[-] con env por
# injector, nombre invalido informado sin escribir (D8).
# ---------------------------------------------------------------------------

_RAICES_3D = {
    "macOS": "/Volumes/estudio/2026/CINE/3D",
    "Windows": "L:/VFX/2026/CINE/3D",
    "Linux": "/mnt/estudio/2026/CINE/3D",
}
_RAICES_PREVIEW = {
    "macOS": "/Volumes/estudio/2026/CINE/PREVIEW",
    "Windows": "L:/VFX/2026/CINE/PREVIEW",
    "Linux": "/mnt/estudio/2026/CINE/PREVIEW",
}
_RAICES_MATTE_PAINT = {
    "macOS": "/Volumes/estudio/2026/CINE/MATTE_PAINT",
    "Windows": "L:/VFX/2026/CINE/MATTE_PAINT",
    "Linux": "/mnt/estudio/2026/CINE/MATTE_PAINT",
}


def _perfil_con_extras(perfil, **extras):
    """Copia del perfil 3x3 mas los espacios extra indicados (sin alias)."""
    copia = {esp: dict(raices) for esp, raices in perfil.items()}
    for clave, raices in extras.items():
        copia[clave] = dict(raices)
    return copia


def _estado_unidad_extras(base):
    """estado_unidad realista para extras: ruta vacia -> desconectado-vacia."""
    if not base or not str(base).strip():
        return {
            "conectado": False,
            "ruta": None,
            "detalle": "Ruta base vacia: configure 'Ruta Base' en el nodo.",
        }
    return _marcar_conectado(base)


def _nombres_filas_extra(dialogo):
    """Nombres de los espacios extra renderizados, en orden de fila."""
    return [fila["espacio"] for fila in dialogo.filas_extras]


def _construir_dialogo_extras(tmp_path, qtbot, perfil, so="macOS", usuario="ana", perfiles=None):
    """Store ficticio con canonico + extras y dialogo en modo normal."""
    ruta = _escribir_store(tmp_path, {usuario: perfil})
    estado = path_manager.estado_panel(ruta, usuario, so)
    dialogo = _construir_dialogo(
        path_manager_panel.PathManagerDialog,
        estado, usuario, ruta, so,
        perfiles=perfiles or [usuario], qtbot=qtbot,
    )
    return dialogo, ruta


def test_extras_subarbol_separado_y_oculto_hasta_checkbox_avanzado(qtbot, monkeypatch, tmp_path):
    """Spec 'canonical key order stays intact': los extras viven en un subarbol
    SEPARADO de ``grupo_avanzado``, oculto con el checkbox desmarcado."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, _ = _construir_dialogo_extras(tmp_path, qtbot, perfil)

    assert hasattr(dialogo, "grupo_extras")
    assert dialogo.grupo_extras is not dialogo.grupo_avanzado
    assert dialogo.grupo_extras.isHidden() is True
    assert list(dialogo.campos_avanzados) == ["COMP", "FROM_VFX", "TO_VFX"]
    assert [f["espacio"] for f in dialogo.filas_extras] == ["3D"]

    dialogo.checkbox_avanzado.setChecked(True)
    assert dialogo.grupo_extras.isHidden() is False


def test_extras_filas_render_nombre_ruta_y_semaforo(qtbot, monkeypatch, tmp_path):
    """Spec 'extra rows render from the profile': dos filas con nombre, raiz
    del SO detectado y estado de unidad (D2: default = ``self.so``)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(
        _ROOT_2026, **{"MATTE_PAINT": _RAICES_MATTE_PAINT, "3D": _RAICES_3D}
    )
    dialogo, _ = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    dialogo.checkbox_avanzado.setChecked(True)

    assert _nombres_filas_extra(dialogo) == ["3D", "MATTE_PAINT"]
    fila_3d = dialogo.filas_extras[0]
    fila_matte = dialogo.filas_extras[1]
    assert fila_3d["combo_so"].currentText() == "macOS"
    assert fila_3d["campo"].text() == "/Volumes/estudio/2026/CINE/3D"
    assert fila_matte["campo"].text() == "/Volumes/estudio/2026/CINE/MATTE_PAINT"
    assert fila_3d["semaforo"].text().startswith("OK")
    assert fila_matte["semaforo"].text().startswith("OK")


def test_extras_etiqueta_so_muestra_so_detectado(qtbot, monkeypatch, tmp_path):
    """Spec: la etiqueta de informacion muestra el SO detectado (self.so)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, _ = _construir_dialogo_extras(tmp_path, qtbot, perfil)

    assert "macOS" in dialogo.etiqueta_so_extras.text()


def test_extras_os_switch_desconecta_y_restaura(qtbot, monkeypatch, tmp_path):
    """Spec 'per-row OS selector switches the slot': sin raiz Windows la fila
    muestra el estado desconectado de 'Ruta base vacia' y al volver a macOS
    restaura raiz y semaforo."""
    monkeypatch.setattr(entorno, "estado_unidad", _estado_unidad_extras)
    perfil = _perfil_con_extras(
        _ROOT_2026, **{"3D": {"macOS": "/Volumes/estudio/2026/CINE/3D"}}
    )
    dialogo, _ = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    dialogo.checkbox_avanzado.setChecked(True)
    fila = dialogo.filas_extras[0]

    fila["combo_so"].setCurrentIndex(fila["combo_so"].findText("Windows"))
    assert fila["campo"].text() == ""
    assert fila["semaforo"].text().startswith("ERROR")
    assert "Ruta base vacia" in fila["semaforo"].text()

    fila["combo_so"].setCurrentIndex(fila["combo_so"].findText("macOS"))
    assert fila["campo"].text() == "/Volumes/estudio/2026/CINE/3D"
    assert fila["semaforo"].text().startswith("OK")


def test_agregar_extra_persiste_y_aplica_env(qtbot, monkeypatch, tmp_path):
    """Spec 'add validates, persists and re-applies env': 'preview' persiste
    como PREVIEW y el env aplicado lleva PYTHON_PREVIEW (via injector)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)

    dialogo.campo_nombre_extra.setText("preview")
    dialogo.campo_ruta_extra.setText("/Volumes/estudio/2026/CINE/PREVIEW")
    dialogo.boton_agregar_extra.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["PREVIEW"]["macOS"] == "/Volumes/estudio/2026/CINE/PREVIEW"
    assert guardado["ana"]["3D"] == _RAICES_3D
    assert aplicados[-1]["PYTHON_PREVIEW"] == "/Volumes/estudio/2026/CINE/PREVIEW"
    assert cacheados[-1] == aplicados[-1]
    assert _nombres_filas_extra(dialogo) == ["3D", "PREVIEW"]
    assert fake_nuke.messages, "el add informa al artista via nuke.message"


def test_agregar_extra_nombre_invalido_informa_sin_escribir(qtbot, monkeypatch, tmp_path):
    """Spec 'invalid name is surfaced without write': 'hosts' (R2) se informa
    via nuke.message y NO escribe ni llega env ni aparece fila."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)

    dialogo.campo_nombre_extra.setText("hosts")
    dialogo.campo_ruta_extra.setText("/Volumes/estudio/2026/CINE/HOSTS")
    dialogo.boton_agregar_extra.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado == {"ana": _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})}
    assert cacheados == [] and aplicados == []
    assert _nombres_filas_extra(dialogo) == ["3D"]
    assert fake_nuke.messages, "el nombre invalido se informa via nuke.message"


def test_agregar_extra_nombre_o_ruta_vacio_informa_sin_escribir(qtbot, monkeypatch, tmp_path):
    """Edge del add: nombre o ruta vacios se informan antes de validar (sin
    tocar el store ni el env)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)
    antes = rutas_engine.leer_perfiles(ruta)

    dialogo.campo_nombre_extra.setText("   ")
    dialogo.campo_ruta_extra.setText("/Volumes/estudio/2026/CINE/X")
    dialogo.boton_agregar_extra.click()
    assert rutas_engine.leer_perfiles(ruta) == antes
    assert cacheados == [] and aplicados == []
    assert fake_nuke.messages and "nombre" in fake_nuke.messages[-1]

    dialogo.campo_nombre_extra.setText("preview")
    dialogo.campo_ruta_extra.setText("   ")
    dialogo.boton_agregar_extra.click()
    assert rutas_engine.leer_perfiles(ruta) == antes
    assert cacheados == [] and aplicados == []
    assert fake_nuke.messages and "ruta" in fake_nuke.messages[-1]


def test_agregar_extra_so_del_combo_slot_del_so_elegido(qtbot, monkeypatch, tmp_path):
    """D2: el add usa el SO del combo de la fila nueva (default self.so, pero
    el artista puede cambiar el slot donde aterriza la raiz)."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)
    dialogo.combo_so_extra.setCurrentIndex(
        dialogo.combo_so_extra.findText("Windows")
    )

    dialogo.campo_nombre_extra.setText("preview")
    dialogo.campo_ruta_extra.setText("L:/VFX/2026/CINE/PREVIEW")
    dialogo.boton_agregar_extra.click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["PREVIEW"]["Windows"] == "L:/VFX/2026/CINE/PREVIEW"
    assert "macOS" not in guardado["ana"]["PREVIEW"]
    assert aplicados[-1]["PYTHON_PREVIEW"] == "L:/VFX/2026/CINE/PREVIEW"
    assert fake_nuke.messages, "el add informa al artista via nuke.message"


def test_ok_extra_ruta_vacia_informa_sin_escribir(qtbot, monkeypatch, tmp_path):
    """Edge del OK: ruta vacia en la fila se informa y no escribe nada."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    cacheados, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)
    fila = dialogo.filas_extras[0]
    guardado_antes = rutas_engine.leer_perfiles(ruta)

    fila["campo"].setText("   ")
    fila["boton_ok"].click()

    assert rutas_engine.leer_perfiles(ruta) == guardado_antes
    assert cacheados == [] and aplicados == []
    assert fake_nuke.messages and "ruta" in fake_nuke.messages[-1].lower()


def test_ok_extra_persiste_ruta_editada_y_aplica_env(qtbot, monkeypatch, tmp_path):
    """D6: el OK de una fila extra persiste SOLO el slot (extra, so) via
    preparar_cambio_base y propaga env por injector."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(_ROOT_2026, **{"3D": _RAICES_3D})
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)
    fila = dialogo.filas_extras[0]

    fila["campo"].setText("/Volumes/estudio/2026/CINE/3D_V2")
    fila["boton_ok"].click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert guardado["ana"]["3D"]["macOS"] == "/Volumes/estudio/2026/CINE/3D_V2"
    assert guardado["ana"]["3D"]["Windows"] == "L:/VFX/2026/CINE/3D"
    assert guardado["ana"]["COMP"] == _ROOT_2026["COMP"]
    assert aplicados[-1]["PYTHON_3D"] == "/Volumes/estudio/2026/CINE/3D_V2"
    assert fake_nuke.messages, "el OK informa al artista via nuke.message"


def test_quitar_extra_elimina_fila_y_reaplica_env(qtbot, monkeypatch, tmp_path):
    """Spec 'remove deletes the extra, canonical untouched': el [-] quita la
    fila de 3D, los canonicos quedan y el env re-aplicado no lleva PYTHON_3D."""
    monkeypatch.setattr(entorno, "estado_unidad", _marcar_conectado)
    perfil = _perfil_con_extras(
        _ROOT_2026, **{"3D": _RAICES_3D, "PREVIEW": _RAICES_PREVIEW}
    )
    dialogo, ruta = _construir_dialogo_extras(tmp_path, qtbot, perfil)
    _, aplicados = _spy_aplicar_env(monkeypatch)
    fake_nuke = _NukeFake()
    monkeypatch.setattr(path_manager_panel, "nuke", fake_nuke)
    dialogo.checkbox_avanzado.setChecked(True)
    fila_3d = dialogo.filas_extras[0]

    fila_3d["boton_quitar"].click()

    guardado = rutas_engine.leer_perfiles(ruta)
    assert "3D" not in guardado["ana"]
    assert guardado["ana"]["PREVIEW"] == _RAICES_PREVIEW
    assert guardado["ana"]["COMP"] == _ROOT_2026["COMP"]
    assert "PYTHON_3D" not in aplicados[-1]
    assert _nombres_filas_extra(dialogo) == ["PREVIEW"]
    assert fake_nuke.messages, "el [-] informa al artista via nuke.message"