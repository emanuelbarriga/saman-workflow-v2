"""
SamanTools.ui.path_manager_panel — dialogo fino del Path Manager (Ctrl+Alt+R),
cambio perfil-por-usuario, slice S4 (widget combo + apply-on-select).

Widget THIN sobre el helper puro (D4, precedente ``cambiar_colorspace`` de V1):
recibe por constructor los DATOS ya calculados por el helper — el estado de
``path_manager.estado_panel``, la identidad (``usuario``/store/SO — SIN
hostname, AD2) y la LISTA de perfiles de ``path_manager.listar_perfiles``
(refrescada por ``abrir_dialogo`` en cada open) — y NO computa perfiles, NO
escribe el store y NO muta variables de entorno por su cuenta (REQ-1). La
persistencia viaja por ``preparar_seleccion_perfil`` (apply-on-select, S4),
``preparar_onboarding`` y ``preparar_cambio_base`` POR ESPACIO (S4); la
propagacion del entorno SOLO por ``injector.cachear_env`` +
``injector.aplicar_entorno``. El feedback al artista usa ``nuke.message``
(aceptado en la capa ui, D4).

Combo de perfiles (spec S4): seleccionar un usuario aplica su perfil al
instante — ``preparar_seleccion_perfil`` -> ``cachear_env`` +
``aplicar_entorno`` -> ``_refrescar_reads()`` (re-evalua los Reads para que
``[getenv PROJECT_ROOT]`` resuelva con el env nuevo; nuke-bound y tolerante).
Un ``ValueError`` por store stale (el usuario ya no esta) se informa sin
aplicar env parcial. Un flag ``legacy`` del helper dispara el aviso de
regeneracion de la forma vieja al abrir (el store se regenera en la siguiente
escritura del motor, AD1).

Slice S5 (nombres editables + seleccion por estacion): el onboarding muestra
un campo ``Nombre del perfil`` pre-llenado con el usuario del SO (getpass
SOLO como sugerencia, editable) y crea el perfil con ESE nombre via
``onboarding_perfil``. Un boton ``Renombrar...`` re-keyea el perfil activo
conservando las 9 raices (``renombrar_perfil`` -> combo refrescado). La
precedencia de preseleccion del combo es seleccion guardada de la estacion
(``cargar_seleccion``) > usuario > primer perfil, y aplicar una seleccion
persiste esa eleccion (``guardar_seleccion``) en
``~/.config/saman/seleccion.json`` (local, nunca en el store del proyecto).

Degrade headless (REQ-5, D4): el modulo importa sin PySide (dual import
PySide2->PySide6 con tercer brazo ``None``) y sin nuke (import tolerante);
``abrir_dialogo()`` no crea ventana si no hay sesion grafica o PySide y nunca
lanza hacia arriba.

Ninguna ruta real del estudio: solo raices ficticias
(``/Volumes/estudio/2026``, ``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

try:
    from PySide2 import QtCore, QtWidgets

    QtAlignment = QtCore.Qt
except ImportError:
    try:
        from PySide6 import QtCore, QtWidgets

        QtAlignment = QtCore.Qt.AlignmentFlag
    except ImportError:
        QtCore = None
        QtWidgets = None
        QtAlignment = None

try:
    import nuke
except ImportError:
    nuke = None

from ..core import entorno
from . import injector
from . import path_manager

# Espacios canonicos del esquema 3x3 (mismo orden del motor y del helper).
_ESPACIOS = ("TO_VFX", "COMP", "FROM_VFX")

# Aviso de regeneracion de una entrada con forma VIEJA (spec S4; AD1: la
# escritura del motor regenera la forma nueva, el flag es solo-lectura).
_MENSAJE_LEGACY = (
    "Path Manager: el perfil de '%s' tiene la forma antigua (hosts/default); "
    "se regenerara con la forma nueva al guardar."
)


if QtWidgets is not None:

    class PathManagerDialog(QtWidgets.QDialog):
        """Dialogo fino: renderiza datos del helper y delega submit + entorno.

        Recibe ``estado`` (salida de ``path_manager.estado_panel``), la
        identidad del usuario y la ``perfiles`` (lista de usuarios del store,
        ``path_manager.listar_perfiles``, refrescada por ``abrir_dialogo`` en
        cada open). Modo onboarding (perfil desconocido/legacy): formulario de
        base y submit que persiste via ``preparar_onboarding``. Modo conocido:
        formulario de cambio de base POR ESPACIO via ``preparar_cambio_base``.
        El combo de perfiles aplica el perfil seleccionado al instante
        (``preparar_seleccion_perfil`` -> env -> refresco de Reads). Todos los
        submits propagan el env devuelto con ``cachear_env`` +
        ``aplicar_entorno`` y el feedback viaja por ``nuke.message``.
        """

        def __init__(self, estado, usuario, ruta_store, so, perfiles=None, parent=None, seleccion_path=None):
            super(PathManagerDialog, self).__init__(parent)
            self.estado = estado
            self.usuario = usuario
            self.ruta_store = ruta_store
            self.so = so
            self.perfiles = list(perfiles) if perfiles else []
            self.seleccion_path = seleccion_path
            self.setWindowTitle("Path Manager")
            self.setMinimumWidth(420)
            self._construir_ui()
            if self.estado.get("legacy"):
                self._informar(_MENSAJE_LEGACY % self.usuario)

        def _construir_ui(self):
            """Construye el layout del dialogo a partir del estado del helper."""
            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(10)

            conocido = bool(self.estado.get("conocido"))
            base = self.estado.get("base_actual") or ""
            unidad = self.estado.get("unidad") or {}

            self.combo_perfiles = QtWidgets.QComboBox()
            self.combo_perfiles.addItems(self.perfiles)
            self._preseleccionar_combo()
            # Conectar DESPUES de preseleccionar: solo la interaccion del
            # artista aplica env, nunca la construccion (REQ-1).
            self.combo_perfiles.currentIndexChanged.connect(self._aplicar_seleccion)
            layout.addWidget(self.combo_perfiles)

            if not conocido:
                fila_nombre = QtWidgets.QHBoxLayout()
                fila_nombre.addWidget(QtWidgets.QLabel("Nombre del perfil:"))
                self.campo_nombre = QtWidgets.QLineEdit(self.usuario)
                fila_nombre.addWidget(self.campo_nombre, 1)
                layout.addLayout(fila_nombre)

            if base:
                self.label_perfil = QtWidgets.QLabel("Raiz actual: %s" % base)
            else:
                self.label_perfil = QtWidgets.QLabel(
                    "Onboarding: defina la base del proyecto"
                )
            detalle = unidad.get("detalle") or "desconocida"
            self.label_unidad = QtWidgets.QLabel("Unidad: %s" % detalle)
            self.label_unidad.setAlignment(QtAlignment.AlignLeft)
            layout.addWidget(self.label_perfil)
            layout.addWidget(self.label_unidad)

            fila_espacio = QtWidgets.QHBoxLayout()
            fila_espacio.addWidget(QtWidgets.QLabel("Espacio:"))
            self.combo_espacio = QtWidgets.QComboBox()
            self.combo_espacio.addItems(list(_ESPACIOS))
            segmento = base.rsplit("/", 1)[-1] if base else ""
            self.combo_espacio.setCurrentText(
                segmento if segmento in _ESPACIOS else "COMP"
            )
            fila_espacio.addWidget(self.combo_espacio, 1)
            layout.addLayout(fila_espacio)

            self.campo_base = QtWidgets.QLineEdit(base)
            self.campo_base.setPlaceholderText("/Volumes/estudio/2026")
            layout.addWidget(self.campo_base)

            fila_botones = QtWidgets.QHBoxLayout()
            if conocido:
                self.boton_cambio = QtWidgets.QPushButton("Cambiar base")
                self.boton_cambio.clicked.connect(self.cambiar_base)
                self.boton_renombrar = QtWidgets.QPushButton("Renombrar...")
                self.boton_renombrar.clicked.connect(self.renombrar)
                fila_botones.addWidget(self.boton_cambio)
                fila_botones.addWidget(self.boton_renombrar)
            else:
                self.boton_onboarding = QtWidgets.QPushButton("Onboarding")
                self.boton_onboarding.clicked.connect(self.onboarding)
                fila_botones.addWidget(self.boton_onboarding)
            self.boton_cerrar = QtWidgets.QPushButton("Cerrar")
            self.boton_cerrar.clicked.connect(self.reject)
            fila_botones.addWidget(self.boton_cerrar)
            layout.addLayout(fila_botones)

        def _preseleccionar_combo(self):
            """Precedencia S5: seleccion guardada > usuario > primer perfil.

            La seleccion POR ESTACION (``cargar_seleccion``) manda; si la
            guardada ya no existe en el store (stale) cae al usuario
            (strategy: getpass SOLO como sugerencia, AD2) y, si tampoco, al
            primer perfil. Nunca dispara señales: la construccion no aplica.
            """
            guardada = path_manager.cargar_seleccion(self.ruta_store, self.seleccion_path)
            if guardada in self.perfiles:
                self._elegir_texto(self.combo_perfiles, guardada)
                return
            if self.usuario in self.perfiles:
                self._elegir_texto(self.combo_perfiles, self.usuario)
                return
            if self.perfiles:
                self.combo_perfiles.setCurrentIndex(0)

        @staticmethod
        def _elegir_texto(combo, texto):
            """Selecciona ``texto`` en ``combo`` si existe (sin cambios si no)."""
            indice = combo.findText(texto)
            if indice >= 0:
                combo.setCurrentIndex(indice)

        def _refrescar_combo(self, preseleccion):
            """Reconstruye el combo con la lista actual, SIN disparar env.

            Bloquea señales durante la reconstruccion (post-rename): el refresh
            es silencioso, solo la interaccion del artista aplica env (REQ-1).
            """
            self.combo_perfiles.blockSignals(True)
            try:
                self.combo_perfiles.clear()
                self.combo_perfiles.addItems(self.perfiles)
                self._elegir_texto(self.combo_perfiles, preseleccion)
            finally:
                self.combo_perfiles.blockSignals(False)

        def _informar(self, texto):
            """Feedback al artista via ``nuke.message``; tolerante sin nuke."""
            if nuke is not None:
                nuke.message(texto)

        def _aplicar_resultado(self, resultado, nombre=None):
            """Propaga el env del helper SOLO via injector y cierra el dialogo.

            ``resultado`` es ``{"perfil", "env", "unidad"}`` de
            ``preparar_onboarding``/``preparar_cambio_base``; el widget NUNCA
            escribe variables de entorno directo (REQ-1/REQ-3). ``nombre`` es
            el perfil aplicado (para el onboarding con nombre editable).
            """
            env = resultado.get("env")
            if env:
                injector.cachear_env(env)
                injector.aplicar_entorno(env)
            base = env.get("PROJECT_ROOT") or ""
            activo = nombre or self.usuario
            self._informar(
                "Path Manager: perfil '%s' activo con base '%s'." % (activo, base)
            )
            self.accept()

        def _aplicar_seleccion(self):
            """Apply-on-select (spec S4): aplica el perfil del combo al instante.

            ``preparar_seleccion_perfil`` -> ``cachear_env`` +
            ``aplicar_entorno`` -> ``_refrescar_reads`` para que los
            ``[getenv PROJECT_ROOT]`` de los Reads re-evaluen con el env nuevo.
            Un ``ValueError`` (store stale: el usuario ya no existe) se informa
            y NO se aplica env parcial; el dialogo queda abierto.
            """
            usuario = self.combo_perfiles.currentText()
            if not usuario:
                return
            try:
                resultado = path_manager.preparar_seleccion_perfil(
                    usuario, self.ruta_store, self.so
                )
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            env = resultado.get("env")
            if env:
                injector.cachear_env(env)
                injector.aplicar_entorno(env)
            path_manager.guardar_seleccion(
                self.ruta_store, usuario, self.seleccion_path
            )
            self._refrescar_reads()
            base = env.get("PROJECT_ROOT") or ""
            self._informar(
                "Path Manager: perfil '%s' activo con base '%s'." % (usuario, base)
            )

        def _refrescar_reads(self):
            """Re-evalua los Reads para que ``[getenv PROJECT_ROOT]`` resuelva nuevo.

            nuke-bound y tolerante (sin nuke, sin nodos o nodos rotos -> 0 sin
            lanzar): re-aplica el script del knob ``file`` (``fromScript``) y
            solo recarga (``reload.execute``) los Reads cuya ruta resuelta
            CAMBIO con el env nuevo. Devuelve cuantos recargo.
            """
            if nuke is None:
                return 0
            try:
                nodos = nuke.allNodes("Read")
            except Exception:
                return 0
            recargados = 0
            for nodo in nodos:
                try:
                    if "file" not in nodo.knobs():
                        continue
                    knob = nodo["file"]
                    script = knob.toScript()
                    anterior = knob.value()
                    knob.fromScript(script)
                    if knob.value() != anterior:
                        nodo["reload"].execute()
                        recargados += 1
                except Exception:
                    continue
            return recargados

        def onboarding(self):
            """Submit del onboarding (REQ-2): nombre editable + base + env.

            El perfil se crea con el NOMBRE del campo editable (pre-llenado
            con el usuario del SO como sugerencia) via
            ``path_manager.onboarding_perfil``, que ademas deja activa la
            seleccion por estacion. Un nombre vacio se informa sin crear.
            """
            base = self.campo_base.text().strip()
            if not base:
                self._informar("Path Manager: defina una base antes de confirmar.")
                return
            campo_nombre = getattr(self, "campo_nombre", None)
            nombre = campo_nombre.text().strip() if campo_nombre is not None else self.usuario
            if not nombre:
                self._informar("Path Manager: defina el nombre del perfil.")
                return
            try:
                resultado = path_manager.onboarding_perfil(
                    nombre,
                    self.ruta_store,
                    base,
                    self.so,
                    seleccion_path=self.seleccion_path,
                )
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            self._aplicar_resultado(resultado, nombre=nombre)

        def renombrar(self):
            """Renombra el perfil activo (re-key conserva las 9 raices).

            Input via ``QInputDialog.getText`` con el nombre actual como
            sugerencia; ``path_manager.renombrar_perfil`` hace el
            READ-RENAME-WRITE atomico bajo el lock del motor. Un
            ``ValueError`` (nombre tomado o inexistente) se informa sin
            romper; el combo se refresca y la seleccion por estacion apunta
            al nombre nuevo.
            """
            actual = self.combo_perfiles.currentText()
            if not actual:
                return
            texto, ok = QtWidgets.QInputDialog.getText(
                self, "Renombrar perfil", "Nuevo nombre del perfil:", text=actual
            )
            if not ok:
                return
            nuevo = (texto or "").strip()
            if not nuevo or nuevo == actual:
                return
            try:
                path_manager.renombrar_perfil(self.ruta_store, actual, nuevo)
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            self.perfiles = path_manager.listar_perfiles(self.ruta_store)
            self._refrescar_combo(nuevo)
            path_manager.guardar_seleccion(
                self.ruta_store, nuevo, self.seleccion_path
            )
            self._informar("Path Manager: perfil renombrado a '%s'." % nuevo)

        def cambiar_base(self):
            """Submit del cambio de base POR ESPACIO (REQ-3/S4).

            Helper persiste (READ-MERGE-WRITE del slot ``(espacio, so)``),
            injector aplica el env devuelto.
            """
            nueva = self.campo_base.text().strip()
            espacio = self.combo_espacio.currentText()
            if not nueva:
                self._informar("Path Manager: defina la nueva raiz.")
                return
            try:
                resultado = path_manager.preparar_cambio_base(
                    self.usuario, self.ruta_store, self.so, espacio, nueva
                )
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            self._aplicar_resultado(resultado)


def _identidad_ambiental():
    """Devuelve el ``usuario`` del sistema; tolerante a fallos.

    Capa ui: ``getpass`` esta permitido aqui (mismo patron que
    ``ui/menu.py``); el hostname ya no participa (AD2). Nunca lanza.
    """
    usuario = "artista"
    try:
        import getpass

        usuario = getpass.getuser()
    except Exception:
        pass
    return usuario


def abrir_dialogo(nuke_mod=None, usuario=None, ruta_store=None, so=None, parent=None, seleccion_path=None):
    """Abre el Path Manager de forma modal; degrade silencioso (REQ-5, D4).

    Guardas en orden: sin sesion grafica (``nuke.GUI`` falso o nuke ausente) ->
    sin PySide disponible -> sin datos validos (``estado_panel`` falla) -> no
    crea ventana y devuelve ``None``. Con GUI y PySide relee la LISTA de
    perfiles del store (``path_manager.listar_perfiles``: el combo se refresca
    en CADA open, spec S4), construye el dialogo con el estado del helper y lo
    ejecuta modal (``exec()``). ``seleccion_path`` (opcional) inyecta la ruta
    de la seleccion por estacion (tests); por defecto la local real. Devuelve el
    dialogo o ``None`` si degrada; nunca lanza hacia arriba (target del menu,
    P3: callback de click).
    """
    modulo = nuke_mod if nuke_mod is not None else nuke
    if modulo is not None and not getattr(modulo, "GUI", False):
        return None
    if QtWidgets is None:
        return None
    if usuario is None:
        usuario = _identidad_ambiental()
    if ruta_store is None:
        ruta_store = injector.obtener_ruta_store()
    if so is None:
        so = entorno.detectar_so()
    try:
        estado = path_manager.estado_panel(ruta_store, usuario, so)
        perfiles = path_manager.listar_perfiles(ruta_store)
    except Exception:
        return None
    dialogo = PathManagerDialog(
        estado,
        usuario,
        ruta_store,
        so,
        perfiles=perfiles,
        parent=parent,
        seleccion_path=seleccion_path,
    )
    dialogo.exec()
    return dialogo