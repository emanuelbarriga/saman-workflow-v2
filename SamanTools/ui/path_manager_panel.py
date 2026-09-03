"""
SamanTools.ui.path_manager_panel — dialogo fino del Path Manager (Ctrl+Alt+R),
cambio path-manager-panel, slice P2.

Widget THIN sobre el helper puro (D4, precedente ``cambiar_colorspace`` de V1):
recibe el estado ya calculado por ``path_manager.estado_panel`` y la identidad
(``usuario``/store/SO — SIN hostname, AD2); NO computa perfiles, NO escribe el
store y NO muta variables de entorno por su cuenta. La persistencia viaja por
``preparar_onboarding``/``preparar_cambio_base`` y la propagacion del entorno
SOLO por ``injector.cachear_env`` + ``injector.aplicar_entorno``. El feedback
al artista usa ``nuke.message`` (aceptado en la capa ui, D4).

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


if QtWidgets is not None:

    class PathManagerDialog(QtWidgets.QDialog):
        """Dialogo fino: renderiza datos del helper y delega submit + entorno.

        Recibe ``estado`` (salida de ``path_manager.estado_panel``) y la
        identidad del usuario. Modo onboarding (perfil desconocido/legacy):
        formulario de base y submit que persiste via ``preparar_onboarding``.
        Modo conocido: formulario de cambio de base via
        ``preparar_cambio_base``. Ambos submit propagan el env devuelto con
        ``cachear_env`` + ``aplicar_entorno`` y cierran el dialogo informando
        con ``nuke.message``.
        """

        def __init__(self, estado, usuario, ruta_store, so, parent=None):
            super(PathManagerDialog, self).__init__(parent)
            self.estado = estado
            self.usuario = usuario
            self.ruta_store = ruta_store
            self.so = so
            self.setWindowTitle("Path Manager")
            self.setMinimumWidth(420)
            self._construir_ui()

        def _construir_ui(self):
            """Construye el layout del dialogo a partir del estado del helper."""
            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(10)

            conocido = bool(self.estado.get("conocido"))
            base = self.estado.get("base_actual") or ""
            unidad = self.estado.get("unidad") or {}

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

            self.campo_base = QtWidgets.QLineEdit(base)
            self.campo_base.setPlaceholderText("/Volumes/estudio/2026")
            layout.addWidget(self.campo_base)

            fila_botones = QtWidgets.QHBoxLayout()
            if conocido:
                self.boton_cambio = QtWidgets.QPushButton("Cambiar base")
                self.boton_cambio.clicked.connect(self.cambiar_base)
                fila_botones.addWidget(self.boton_cambio)
            else:
                self.boton_onboarding = QtWidgets.QPushButton("Onboarding")
                self.boton_onboarding.clicked.connect(self.onboarding)
                fila_botones.addWidget(self.boton_onboarding)
            self.boton_cerrar = QtWidgets.QPushButton("Cerrar")
            self.boton_cerrar.clicked.connect(self.reject)
            fila_botones.addWidget(self.boton_cerrar)
            layout.addLayout(fila_botones)

        def _informar(self, texto):
            """Feedback al artista via ``nuke.message``; tolerante sin nuke."""
            if nuke is not None:
                nuke.message(texto)

        def _aplicar_resultado(self, resultado):
            """Propaga el env del helper SOLO via injector y cierra el dialogo.

            ``resultado`` es ``{"perfil", "env", "unidad"}`` de
            ``preparar_onboarding``/``preparar_cambio_base``; el widget NUNCA
            escribe variables de entorno directo (REQ-1/REQ-3).
            """
            env = resultado.get("env")
            if env:
                injector.cachear_env(env)
                injector.aplicar_entorno(env)
            base = env.get("PROJECT_ROOT") or ""
            self._informar(
                "Path Manager: perfil '%s' activo con base '%s'." % (self.usuario, base)
            )
            self.accept()

        def onboarding(self):
            """Submit del onboarding (REQ-2): persiste y aplica el env."""
            base = self.campo_base.text().strip()
            if not base:
                self._informar("Path Manager: defina una base antes de confirmar.")
                return
            try:
                resultado = path_manager.preparar_onboarding(
                    self.usuario, self.ruta_store, base, self.so
                )
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            self._aplicar_resultado(resultado)

        def cambiar_base(self):
            """Submit del cambio de base (REQ-3): helper persiste, injector aplica."""
            nueva = self.campo_base.text().strip()
            if not nueva:
                self._informar("Path Manager: defina la nueva base.")
                return
            try:
                resultado = path_manager.preparar_cambio_base(
                    self.usuario, self.ruta_store, self.so, nueva
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


def abrir_dialogo(nuke_mod=None, usuario=None, ruta_store=None, so=None, parent=None):
    """Abre el Path Manager de forma modal; degrade silencioso (REQ-5, D4).

    Guardas en orden: sin sesion grafica (``nuke.GUI`` falso o nuke ausente) ->
    sin PySide disponible -> sin datos validos (``estado_panel`` falla) -> no
    crea ventana y devuelve ``None``. Con GUI y PySide construye el dialogo
    con el estado del helper y lo ejecuta modal (``exec()``). Devuelve el
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
    except Exception:
        return None
    dialogo = PathManagerDialog(estado, usuario, ruta_store, so, parent=parent)
    dialogo.exec()
    return dialogo