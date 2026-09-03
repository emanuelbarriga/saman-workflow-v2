"""
SamanTools.ui.path_manager_panel — dialogo fino del Path Manager (Ctrl+Alt+R),
rediseno UX segun el mockup del usuario (modo normal / onboarding / avanzado).

Widget THIN sobre el helper puro (D4, precedente ``cambiar_colorspace`` de V1):
recibe por constructor los DATOS ya calculados por el helper — el estado de
``path_manager.estado_panel``, la identidad (``usuario``/store/SO — SIN
hostname, AD2) y la LISTA de perfiles de ``path_manager.listar_perfiles``
(refrescada por ``abrir_dialogo`` en cada open) — y NO computa perfiles, NO
escribe el store y NO muta variables de entorno por su cuenta (REQ-1). La
persistencia viaja por ``preparar_seleccion_perfil`` (apply-on-select, S4),
``preparar_onboarding``, ``preparar_cambio_base`` POR ESPACIO (modo avanzado)
y ``guardar_base_unificada`` (modo simple, TODOS); la propagacion del entorno
SOLO por ``injector.cachear_env`` + ``injector.aplicar_entorno`` y el refresco
de Reads por ``_refrescar_reads``. El feedback al artista usa ``nuke.message``
(aceptado en la capa ui, D4).

Tres modos (mockup vinculante):

  * Normal (perfil conocido): combo de perfiles con apply-on-select (seleccion
    aplica al instante Y guarda la seleccion por estacion — comportamiento S4
    intacto, NO espera a "Guardar y Aplicar"), semaforo del disco y campo
    "Ruta Base del Proyecto" con boton "Buscar carpeta...". Un QCheckBox
    "Configuracion avanzada" (desmarcado por defecto) alterna el modo simple
    (UNA base -> ``guardar_base_unificada`` escribe los TRES espacios del SO
    actual) y el modo avanzado (tres campos simultaneos COMP / FROM_VFX /
    TO_VFX, en el orden del mockup, con sus rutas actuales del perfil,
    "Buscar..." y semaforo propio por ``estado_unidad``; cada campo escribe
    SOLO su espacio via ``preparar_cambio_base``). Botones: Renombrar Perfil,
    Guardar y Aplicar, Cerrar.
  * Onboarding (desconocido/legacy): banner informativo, campo "Nombre del
    Perfil" editable (getpass SOLO como sugerencia, S5), "Ruta Base de
    Trabajo" + "Buscar carpeta...", semaforo del montaje y boton primario
    "Crear Perfil y Vincular" (nunca "Onboarding"). Sin checkbox avanzado:
    la primera vez es simple; se pasa a avanzado renombrando/guardando.
  * Avanzado (checkbox marcado): los tres campos a la vista a la vez en el
    orden COMP, FROM_VFX, TO_VFX (Scripts de Nuke / Plates-entrada /
    Renders-salidas); valores actuales del perfil y semaforo propio por campo.

"Guardar y Aplicar" (opcion A): persiste las rutas EDITADAS de los campos
para el perfil activo del combo y, tras guardar, propaga el env via injector
y refresca los Reads. El semaforo usa ``entorno.estado_unidad`` (timeout +
cache ~10s del motor): nunca se cuelga en un mount muerto ni martilla el
disco. La paleta es minima (verde OK / rojo ERROR) alineada a los tonos
oscuros de Nuke, sin re-temas globales.

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

# Modo avanzado: orden del mockup (COMP, FROM_VFX, TO_VFX) + descripcion; el
# esquema guarda las mismas claves canonicas.
_AVANZADOS = (
    ("COMP", "Scripts de Nuke"),
    ("FROM_VFX", "Plates / entrada"),
    ("TO_VFX", "Renders y salidas"),
)

_TITULO_NORMAL = "Path Manager — Nuke"
_TITULO_ONBOARDING = "Path Manager — Bienvenido"

_MENSAJE_BANNER_ONBOARDING = (
    "No se encontro un perfil asignado a este equipo. "
    "Configura tu perfil para vincular las rutas de trabajo."
)

# Paleta del semaforo alineada a los tonos oscuros de Nuke (verde/rojo),
# via hoja minima en labels — sin re-temas globales.
_ESTILO_OK = "color: #4ade80; font-weight: bold;"
_ESTILO_ERROR = "color: #f87171; font-weight: bold;"

# Aviso de regeneracion de una entrada con forma VIEJA (spec S4; AD1: la
# escritura del motor regenera la forma nueva, el flag es solo-lectura).
_MENSAJE_LEGACY = (
    "Path Manager: el perfil de '%s' tiene la forma antigua (hosts/default); "
    "se regenerara con la forma nueva al guardar."
)


def _texto_semaforo(estado):
    """Texto legible del semaforo dado el dict de ``entorno.estado_unidad``.

    Pura (sin Qt): verde → ``OK — Conectado — <ruta>``; rojo →
    ``ERROR — Desconectado — <detalle>``. El dict viene del motor (timeout +
    cache ~10s), nunca del panel.
    """
    if estado.get("conectado"):
        ruta = estado.get("ruta") or ""
        return "OK — Conectado — %s" % ruta
    detalle = estado.get("detalle") or "Desconectado."
    return "ERROR — Desconectado — %s" % detalle


def _hoja_semaforo(estado):
    """Hoja de estilo del semaforo: verde OK / rojo ERROR (paleta Nuke)."""
    if estado.get("conectado"):
        return _ESTILO_OK
    return _ESTILO_ERROR


if QtWidgets is not None:

    class PathManagerDialog(QtWidgets.QDialog):
        """Dialogo fino: renderiza datos del helper y delega submit + entorno.

        Recibe ``estado`` (salida de ``path_manager.estado_panel``), la
        identidad del usuario y la ``perfiles`` (lista de usuarios del store,
        ``path_manager.listar_perfiles``, refrescada por ``abrir_dialogo`` en
        cada open). Modo onboarding (perfil desconocido/legacy): banner,
        campo de nombre editable y submit via ``preparar_onboarding``. Modo
        conocido: formulario base/avanzado — "Guardar y Aplicar" persiste
        via ``guardar_base_unificada`` (simple, TODOS) o
        ``preparar_cambio_base`` por espacio (avanzado). El combo de perfiles
        aplica el perfil seleccionado al instante (``preparar_seleccion_perfil``
        -> env -> refresco de Reads) y SINCRONIZA los campos con el perfil
        activo. Todos los submits propagan el env devuelto con ``cachear_env``
        + ``aplicar_entorno`` y el feedback viaja por ``nuke.message``.
        """

        def __init__(self, estado, usuario, ruta_store, so, perfiles=None, parent=None, seleccion_path=None):
            super(PathManagerDialog, self).__init__(parent)
            self.estado = estado
            self.usuario = usuario
            self.ruta_store = ruta_store
            self.so = so
            self.perfiles = list(perfiles) if perfiles else []
            self.seleccion_path = seleccion_path
            self._construir_ui()
            if self.estado.get("legacy"):
                self._informar(_MENSAJE_LEGACY % self.usuario)

        def _construir_ui(self):
            """Construye el layout del dialogo a partir del estado del helper."""
            layout = QtWidgets.QVBoxLayout(self)
            layout.setSpacing(10)

            conocido = bool(self.estado.get("conocido"))
            self.setWindowTitle(_TITULO_NORMAL if conocido else _TITULO_ONBOARDING)
            self.setMinimumWidth(460)

            self.campos_avanzados = {}
            self.semaforos_avanzados = {}

            if conocido:
                self._construir_modo_normal(layout)
            else:
                self._construir_modo_onboarding(layout)

        def _construir_modo_normal(self, layout):
            """Forma del modo normal/avanzado (mockup, opcion A)."""
            fila_perfil = QtWidgets.QHBoxLayout()
            fila_perfil.addWidget(QtWidgets.QLabel("Perfil Activo:"))
            self.combo_perfiles = QtWidgets.QComboBox()
            self.combo_perfiles.addItems(self.perfiles)
            self._preseleccionar_combo()
            # Conectar DESPUES de preseleccionar: solo la interaccion del
            # artista aplica env, nunca la construccion (REQ-1).
            self.combo_perfiles.currentIndexChanged.connect(self._aplicar_seleccion)
            fila_perfil.addWidget(self.combo_perfiles, 1)
            layout.addLayout(fila_perfil)

            self.contenedor_simple = QtWidgets.QWidget()
            cont = QtWidgets.QVBoxLayout(self.contenedor_simple)
            cont.setContentsMargins(0, 0, 0, 0)
            cont.setSpacing(10)

            self.campo_base = QtWidgets.QLineEdit()
            self.campo_base.setPlaceholderText("/Volumes/estudio/2026")
            self.boton_buscar_base = QtWidgets.QPushButton("Buscar carpeta...")
            self.boton_buscar_base.clicked.connect(
                lambda: self._buscar_carpeta(self.campo_base)
            )

            fila_estado = QtWidgets.QHBoxLayout()
            fila_estado.addWidget(QtWidgets.QLabel("Estado del Disco:"))
            self.semaforo_base = QtWidgets.QLabel()
            self.semaforo_base.setWordWrap(True)
            self.campo_base.editingFinished.connect(
                lambda: self._actualizar_semaforo(self.campo_base, self.semaforo_base)
            )
            fila_estado.addWidget(self.semaforo_base, 1)
            cont.addLayout(fila_estado)

            fila_base = QtWidgets.QHBoxLayout()
            fila_base.addWidget(QtWidgets.QLabel("Ruta Base del Proyecto:"))
            fila_base.addWidget(self.campo_base, 1)
            fila_base.addWidget(self.boton_buscar_base)
            cont.addLayout(fila_base)
            layout.addWidget(self.contenedor_simple)

            self.checkbox_avanzado = QtWidgets.QCheckBox(
                "Configuracion avanzada "
                "(Discos distintos para COMP / Plates / Render)"
            )
            self.checkbox_avanzado.toggled.connect(self._alternar_avanzado)
            layout.addWidget(self.checkbox_avanzado)

            self.grupo_avanzado = QtWidgets.QWidget()
            grupo = QtWidgets.QVBoxLayout(self.grupo_avanzado)
            grupo.setContentsMargins(0, 0, 0, 0)
            grupo.setSpacing(6)
            self.botones_buscar_avanzados = {}
            for espacio, descripcion in _AVANZADOS:
                fila = QtWidgets.QHBoxLayout()
                etiqueta = QtWidgets.QLabel("%s (%s)" % (espacio, descripcion))
                etiqueta.setMinimumWidth(170)
                fila.addWidget(etiqueta)
                campo = QtWidgets.QLineEdit()
                campo.setPlaceholderText("/Volumes/estudio/2026")
                boton = QtWidgets.QPushButton("Buscar...")
                semaforo = QtWidgets.QLabel()
                semaforo.setWordWrap(True)
                boton.clicked.connect(
                    lambda _checked=False, c=campo: self._buscar_carpeta(c)
                )
                campo.editingFinished.connect(
                    lambda c=campo, s=semaforo: self._actualizar_semaforo(c, s)
                )
                fila.addWidget(campo, 1)
                fila.addWidget(boton)
                grupo.addLayout(fila)
                fila_semaforo = QtWidgets.QHBoxLayout()
                sangria = QtWidgets.QLabel("  ")
                sangria.setFixedWidth(170)
                fila_semaforo.addWidget(sangria)
                fila_semaforo.addWidget(semaforo, 1)
                grupo.addLayout(fila_semaforo)
                self.campos_avanzados[espacio] = campo
                self.semaforos_avanzados[espacio] = semaforo
                self.botones_buscar_avanzados[espacio] = boton
            self.grupo_avanzado.setVisible(False)
            layout.addWidget(self.grupo_avanzado)

            fila_botones = QtWidgets.QHBoxLayout()
            self.boton_renombrar = QtWidgets.QPushButton("Renombrar Perfil")
            self.boton_renombrar.clicked.connect(self.renombrar)
            self.boton_guardar = QtWidgets.QPushButton("Guardar y Aplicar")
            self.boton_guardar.clicked.connect(self.guardar)
            self.boton_cerrar = QtWidgets.QPushButton("Cerrar")
            self.boton_cerrar.clicked.connect(self.reject)
            fila_botones.addWidget(self.boton_renombrar)
            fila_botones.addWidget(self.boton_guardar)
            fila_botones.addWidget(self.boton_cerrar)
            layout.addLayout(fila_botones)

            if self.combo_perfiles.currentText():
                self._refrescar_campos_activo()

        def _construir_modo_onboarding(self, layout):
            """Forma del onboarding (mockup): banner + nombre + base + montaje."""
            self.banner = QtWidgets.QLabel(_MENSAJE_BANNER_ONBOARDING)
            self.banner.setWordWrap(True)
            self.banner.setStyleSheet("color: #d4d4d4;")
            layout.addWidget(self.banner)

            fila_nombre = QtWidgets.QHBoxLayout()
            fila_nombre.addWidget(QtWidgets.QLabel("Nombre del Perfil:"))
            self.campo_nombre = QtWidgets.QLineEdit(self.usuario)
            fila_nombre.addWidget(self.campo_nombre, 1)
            layout.addLayout(fila_nombre)

            fila_base = QtWidgets.QHBoxLayout()
            fila_base.addWidget(QtWidgets.QLabel("Ruta Base de Trabajo:"))
            self.campo_base = QtWidgets.QLineEdit()
            self.campo_base.setPlaceholderText("/Volumes/estudio/2026")
            self.boton_buscar_base = QtWidgets.QPushButton("Buscar carpeta...")
            self.boton_buscar_base.clicked.connect(
                lambda: self._buscar_carpeta(self.campo_base)
            )
            fila_base.addWidget(self.campo_base, 1)
            fila_base.addWidget(self.boton_buscar_base)
            layout.addLayout(fila_base)

            fila_montaje = QtWidgets.QHBoxLayout()
            fila_montaje.addWidget(QtWidgets.QLabel("Estado del Montaje:"))
            self.semaforo_montaje = QtWidgets.QLabel()
            self.semaforo_montaje.setWordWrap(True)
            self.campo_base.editingFinished.connect(
                lambda: self._actualizar_semaforo(self.campo_base, self.semaforo_montaje)
            )
            fila_montaje.addWidget(self.semaforo_montaje, 1)
            layout.addLayout(fila_montaje)
            self._aplicar_estado_semaforo(
                self.estado.get("unidad") or {}, self.semaforo_montaje
            )

            fila_botones = QtWidgets.QHBoxLayout()
            self.boton_onboarding = QtWidgets.QPushButton("Crear Perfil y Vincular")
            self.boton_onboarding.clicked.connect(self.onboarding)
            self.boton_cerrar = QtWidgets.QPushButton("Cerrar")
            self.boton_cerrar.clicked.connect(self.reject)
            fila_botones.addWidget(self.boton_onboarding)
            fila_botones.addWidget(self.boton_cerrar)
            layout.addLayout(fila_botones)

        def _alternar_avanzado(self, avanzado):
            """Alterna modo simple (una base) <-> avanzado (tres campos)."""
            self.contenedor_simple.setVisible(not avanzado)
            self.grupo_avanzado.setVisible(avanzado)

        def _aplicar_estado_semaforo(self, estado, label):
            """Vuelca un dict de ``estado_unidad`` en el QLabel (texto + hoja)."""
            label.setText(_texto_semaforo(estado))
            label.setStyleSheet(_hoja_semaforo(estado))

        def _actualizar_semaforo(self, campo, label):
            """Actualiza el semaforo ``label`` desde el texto del ``campo``.

            Delega en ``entorno.estado_unidad`` (timeout + cache ~10s del
            motor): nunca se cuelga en un mount muerto ni martilla el disco.
            """
            self._aplicar_estado_semaforo(entorno.estado_unidad(campo.text()), label)

        def _buscar_carpeta(self, campo):
            """'Buscar carpeta...': QFileDialog.getExistingDirectory tolerante.

            Rellena ``campo`` con la carpeta elegida; si el usuario cancela o
            Qt falla (dialogo sin file picker), no hace nada. La ruta inicial
            es la del campo (si tiene).
            """
            inicial = campo.text().strip()
            try:
                elegida = QtWidgets.QFileDialog.getExistingDirectory(
                    self, "Buscar carpeta", inicial
                )
            except Exception:
                return
            if elegida:
                campo.setText(elegida)

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

        def _refrescar_campos_activo(self):
            """Sincroniza campo base + campos avanzados con el perfil del combo.

            Lectura pura via ``path_manager.raices_para_so`` (relee el store;
            nunca escribe): la base es la primera raiz no-None del SO actual
            (orden canonico) y cada campo avanzado su raiz. Refresca tambien
            los semaforos de cada campo (cache del motor).
            """
            activo = self.combo_perfiles.currentText()
            if not activo:
                return
            raices = path_manager.raices_para_so(activo, self.ruta_store, self.so)
            if not raices:
                return
            base = next(
                (raices.get(espacio) for espacio in _ESPACIOS if raices.get(espacio)),
                "",
            )
            self.campo_base.setText(base or "")
            self._actualizar_semaforo(self.campo_base, self.semaforo_base)
            for espacio, campo in self.campos_avanzados.items():
                campo.setText(raices.get(espacio) or "")
                self._actualizar_semaforo(campo, self.semaforos_avanzados[espacio])

        def _informar(self, texto):
            """Feedback al artista via ``nuke.message``; tolerante sin nuke."""
            if nuke is not None:
                nuke.message(texto)

        def _aplicar_resultado(self, resultado, nombre=None):
            """Propaga el env del helper SOLO via injector, refresca Reads y cierra.

            ``resultado`` es ``{"perfil", "env", "unidad"}`` del helper; el
            widget NUNCA escribe variables de entorno directo (REQ-1/REQ-3).
            ``nombre`` es el perfil aplicado (para el submit con nombre).
            """
            env = resultado.get("env")
            if env:
                injector.cachear_env(env)
                injector.aplicar_entorno(env)
            self._refrescar_reads()
            base = env.get("PROJECT_ROOT") or ""
            activo = nombre or self.combo_perfiles.currentText() or self.usuario
            self._informar(
                "Path Manager: perfil '%s' activo con base '%s'." % (activo, base)
            )
            self.accept()

        def _aplicar_seleccion(self):
            """Apply-on-select (spec S4): aplica el perfil del combo al instante.

            ``preparar_seleccion_perfil`` -> ``cachear_env`` +
            ``aplicar_entorno`` -> campos sincronizados con el perfil +
            ``_refrescar_reads`` para que los ``[getenv PROJECT_ROOT]`` de los
            Reads re-evaluen con el env nuevo. Un ``ValueError`` (store stale:
            el usuario ya no existe) se informa y NO se aplica env parcial; el
            dialogo queda abierto.
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
            self._refrescar_campos_activo()
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
            seleccion por estacion. Un nombre o base vacios se informan sin
            crear.
            """
            base = self.campo_base.text().strip()
            if not base:
                self._informar("Path Manager: defina una base antes de confirmar.")
                return
            nombre = getattr(self, "campo_nombre", None)
            nombre_texto = nombre.text().strip() if nombre is not None else self.usuario
            if not nombre_texto:
                self._informar("Path Manager: defina el nombre del perfil.")
                return
            try:
                resultado = path_manager.onboarding_perfil(
                    nombre_texto,
                    self.ruta_store,
                    base,
                    self.so,
                    seleccion_path=self.seleccion_path,
                )
            except ValueError as error:
                self._informar("Path Manager: %s" % error)
                return
            self._aplicar_resultado(resultado, nombre=nombre_texto)

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

        def guardar(self):
            """Submit del 'Guardar y Aplicar' (opcion A): persiste rutas editadas.

            Modo simple (checkbox desmarcado): la base del campo 'Ruta Base
            del Proyecto' se persiste en los TRES espacios del SO actual via
            ``path_manager.guardar_base_unificada`` (modo TODOS). Modo
            avanzado: CADA campo persiste SOLO su espacio via
            ``path_manager.preparar_cambio_base`` (per-space) con el env final
            del ultimo resultado. Ambas rutas propagan env por injector y
            refrescan Reads via ``_aplicar_resultado``.
            """
            activo = self.combo_perfiles.currentText()
            if not activo:
                return
            resultado = None
            if self.checkbox_avanzado.isChecked():
                pendientes = {}
                for espacio, campo in self.campos_avanzados.items():
                    texto = campo.text().strip()
                    if not texto:
                        self._informar(
                            "Path Manager: defina la ruta de '%s'." % espacio
                        )
                        return
                    pendientes[espacio] = texto
                for espacio, ruta_nueva in pendientes.items():
                    try:
                        resultado = path_manager.preparar_cambio_base(
                            activo, self.ruta_store, self.so, espacio, ruta_nueva
                        )
                    except ValueError as error:
                        self._informar("Path Manager: %s" % error)
                        return
            else:
                base = self.campo_base.text().strip()
                if not base:
                    self._informar("Path Manager: defina la ruta base del proyecto.")
                    return
                try:
                    resultado = path_manager.guardar_base_unificada(
                        activo, self.ruta_store, self.so, base
                    )
                except ValueError as error:
                    self._informar("Path Manager: %s" % error)
                    return
            self._aplicar_resultado(resultado, nombre=activo)


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