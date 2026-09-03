"""
SamanTools.ui.menu — target de ejecucion del bootstrap V2 (change load-contract, slice H4).

Este modulo es el archivo que ejecuta ``bootstrap/menu.py`` (``_cargar_menu_real``)
cuando el checkout esta completo: registra los callbacks del injector
(``registrar_callbacks``) exactamente UNA vez y construye el menu minimo
SamanTools. Es la capa ui del paquete y la UNICA que importa ``nuke`` a nivel
de modulo (0% coverage aceptado por diseno, ADR-7).

  - ``registrar_callbacks``: bind de ``nuke.addOnScriptLoad``/``addOnScriptSave``.
    En load resuelve la identidad ambiental (getpass/socket, permitido en la
    capa ui), detecta el SO (``core.entorno.detectar_so``), calcula la raiz de
    proyecto por corte estructural (``raiz_proyecto_desde_ruta``), resuelve el
    store (``obtener_ruta_store(raiz_proyecto)``, AD5 proyecto-primero) y el
    perfil (``resolver_perfil``, con onboarding ficticio si no existe), arma
    el contexto desde ``nuke.root().name()``, aplica el override manual
    ``project_directory`` de la root (ADR-5) y decide por la cadena de
    precedencia (ADR-3: env pre-existente del render farm gana -> override
    manual gana -> env recien armado del perfil). Al final cachea y aplica el
    env (``cachear_env`` + ``aplicar_entorno``). En save re-afirma SOLO el env
    cacheado en memoria (ADR-2: nunca store, lock ni motor).
  - ``instalar``: registra los callbacks y construye el menu SamanTools >
    Configuracion con UN item de informacion de version; idempotente (no
    duplica items). Los botones de mantenimiento (Actualizar/Desinstalar) los
    agrega el PROPIO bootstrap despues, sobre el mismo submenu
    (``bootstrap/menu.py`` ``_agregar_boton_menu``).
  - Item "Path Manager..." (cambio path-manager-panel, P3): PLANO sobre el
    menu SamanTools (D5), atajo ``Ctrl+Alt+R`` desde la constante unica
    ``_ATAJO_PATH_MANAGER`` con fallback ``Ctrl+Alt+O`` ante colision (REQ-3);
    su callback ``_abrir_path_manager`` importa el panel SOLO en el click (D1)
    — nunca PySide a nivel de modulo (REQ-2).
  - Import-safe: importa el injector y el core normalmente; el shim
    (``SamanTools.rutas``) se importa TOLERANTEMENTE (try/except ImportError)
    para que un shim roto nunca rompa callbacks ni menu (spec load-ui-menu).
    NO crea paneles y NO importa PySide.

Layering: ``SamanTools/core`` NO se toca. Ninguna ruta real del estudio: solo
raices ficticias (``/Volumes/estudio/2026``, ``L:/VFX/2026``,
``/mnt/estudio/2026``).
"""

import os
import sys

# El bootstrap exec este archivo con un namespace minimo (__file__/__name__,
# sin __package__): la raiz del checkout (dos niveles arriba de este archivo)
# se auto-anade a sys.path — mismo patron que el menu.py raiz de V1 — para que
# `from SamanTools import ...` resuelva dentro de Nuke. Idempotente.
_RAIZ_CHECKOUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ_CHECKOUT not in sys.path:
    sys.path.append(_RAIZ_CHECKOUT)

import nuke  # capa ui: unico modulo del paquete que importa nuke a nivel top

from SamanTools.core import entorno
from SamanTools.core import rutas_engine
from SamanTools.ui import injector

try:
    from SamanTools import rutas  # noqa: F401  shim compat V1; import tolerante
except ImportError:
    rutas = None

_NOMBRE_MENU = "SamanTools"
_NOMBRE_SUBMENU = "Configuración"
_NOMBRE_ITEM_INFO = "Información de SamanTools..."
_NOMBRE_ITEM_PATH_MANAGER = "Path Manager..."
_ATAJO_PATH_MANAGER = "Ctrl+Alt+R"
_ATAJO_FALLBACK_PATH_MANAGER = "Ctrl+Alt+O"
_CLAVE_PROJECT_ROOT = "PROJECT_ROOT"


def registrar_callbacks():
    """Registra ``addOnScriptLoad``/``addOnScriptSave`` UNA sola vez.

    Idempotente via ``injector._callbacks_registrados`` (ADR-7): el flag vive
    en el injector, que sys.modules cachea entre re-ejecuciones del bootstrap
    (cada exec de este archivo recibe un namespace fresco, pero el paquete y
    el injector persisten).
    """
    if injector._callbacks_registrados:
        return
    nuke.addOnScriptLoad(_al_cargar_script)
    nuke.addOnScriptSave(_al_guardar_script)
    injector._callbacks_registrados = True


# --- Identidad ambiental (capa ui: getpass/socket permitidos aqui) -------------


def _identidad_ambiental():
    """Identidad (usuario, hostname) del sistema; tolerante a fallos."""
    usuario = "artista"
    hostname = "localhost"
    try:
        import getpass

        usuario = getpass.getuser()
    except Exception:
        pass
    try:
        import socket

        hostname = socket.gethostname()
    except Exception:
        pass
    return usuario, hostname


def _resolver_contexto_carga():
    """Resuelve (perfil, override, ruta_plato) del flujo de load, sin efectos.

    Orden: ruta del script (``nuke.root().name()``) + override manual (knob
    ``project_directory``, ADR-5) -> identidad (SOLO usuario, AD2/AD10 — sin
    hostname) -> raiz de proyecto por CORTE ESTRUCTURAL
    (``raiz_proyecto_desde_ruta``) inyectada a ``obtener_ruta_store`` (AD5:
    el store del proyecto gana si existe; la cadena cae al env/config si no)
    -> perfil (``resolver_perfil`` SOLO por usuario, con onboarding a store
    ficticio si el perfil no existe). Tolerante: cualquier fallo devuelve
    ``perfil=None`` y el flujo de carga no escribe nada.
    """
    override = None
    ruta_plato = ""
    try:
        root = nuke.root()
        if root is not None:
            ruta_plato = str(getattr(root, "name", lambda: "")() or "")
            override = injector._override_proyecto_desde_root(root)
    except Exception:
        pass
    try:
        usuario, _hostname = _identidad_ambiental()
        raiz_proyecto = entorno.raiz_proyecto_desde_ruta(ruta_plato)
        ruta_store = injector.obtener_ruta_store(raiz_proyecto)
        perfil = rutas_engine.resolver_perfil(usuario, ruta_store)
    except Exception:
        return None, None, ""
    return perfil, override, ruta_plato


def _al_cargar_script():
    """addOnScriptLoad: aplica la cadena de precedencia del entorno (ADR-3/4/5).

    Render farm/headless (``PROJECT_ROOT`` ya pre-existente ANTES de que el
    loader escriba) -> no-op sin perfil ni onboarding (ADR-4). Si no: perfil
    resuelto (onboarding ficticio si falta) -> env ensamblado con la base del
    override manual si existe -> ``_aplicar_precedencia`` -> ``cachear_env`` +
    ``aplicar_entorno``. Nunca lanza: un fallo deja el entorno como estaba.
    """
    if str(os.environ.get(_CLAVE_PROJECT_ROOT) or "").strip():
        return
    try:
        perfil, override, ruta_plato = _resolver_contexto_carga()
        if perfil is None:
            return
        so = entorno.detectar_so()
        env = injector.armar_estado_env(perfil, so, ruta_plato, base=override)
        final = injector._aplicar_precedencia(env, override, dict(os.environ))
        if final:
            injector.cachear_env(final)
            injector.aplicar_entorno(final)
    except Exception:
        pass


def _al_guardar_script():
    """addOnScriptSave: re-afirma SOLO el env cacheado en memoria (ADR-2).

    Ni store, ni lock, ni funciones del motor en la ruta de guardado: aplica
    ``_env_cache`` tal cual (no-op si nada fue inyectado esta sesion).
    """
    if not injector._env_cache:
        return
    injector.aplicar_entorno(injector._env_cache)


# --- Menu minimo ---------------------------------------------------------------


def _mostrar_info_version():
    """Item de informacion: version SemVer del paquete + commit si es checkout git."""
    version = "desconocida"
    try:
        from SamanTools import __version__

        version = __version__
    except Exception:
        pass
    commit = ""
    try:
        import subprocess

        r = subprocess.run(
            ["git", "-C", _RAIZ_CHECKOUT, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            commit = r.stdout.strip()
    except Exception:
        pass
    if commit:
        nuke.message(
            "SamanTools V2 — versión %s\nCommit: %s" % (version, commit)
        )
    else:
        nuke.message("SamanTools V2 — versión %s" % version)


def _abrir_path_manager():
    """Callback del click "Path Manager...": importa el panel SOLO aqui (D1).

    El import de ``SamanTools.ui.path_manager_panel`` ocurre en el momento del
    click, nunca al instalar: con el llega PySide al proceso (el panel lo
    importa internamente; este modulo no contiene NINGUN literal de import de
    PySide, ni al tope ni indentado — el guard regex de test_menu lo detecta
    con re.M). ``abrir_dialogo`` degrada en silencio sin sesion grafica, asi
    que el callback nunca lanza hacia arriba.
    """
    from SamanTools.ui import path_manager_panel

    path_manager_panel.abrir_dialogo()


def seleccionar_atajo(principal, fallback, ocupado):
    """Elige el atajo a registrar: ``principal`` salvo que este ocupado (D5).

    Pura y testable sin Nuke: ``ocupado`` es un predicado que recibe el atajo
    candidato y devuelve bool. Si ``ocupado(principal)`` es True (otro plugin
    ya registro el atajo), la colision degrada al ``fallback`` documentado; si
    no, se mantiene el ``principal``.
    """
    if ocupado(principal):
        return fallback
    return principal


def _atajo_ocupado(atajo):
    """Predicado real de colision del atajo (D5): optimista, nunca lanza.

    Nuke no expone una consulta de propiedad de atajos (open question en
    design.md) y su ``addCommand`` advierte en vez de lanzar: no hay senal
    fiable de colision, asi que la implementacion real registra de forma
    optimista con el atajo principal. La proteccion try/except garantiza que
    el build del menu jamas se rompe ante una API distinta o futura; los tests
    inyectan el predicado.
    """
    try:
        return False
    except Exception:
        return False


def instalar():
    """Construye el menu minimo SamanTools y registra los callbacks (idempotente).

    Reutiliza el menu/submenu si ya existen (patron V1): los botones de
    mantenimiento del bootstrap (Actualizar/Desinstalar) se agregan DESPUES
    sobre el mismo submenu Configuracion desde ``bootstrap/menu.py``. Registra
    ademas el item "Path Manager..." PLANO sobre el menu SamanTools (D5) con
    el atajo de la constante ``_ATAJO_PATH_MANAGER`` (fallback
    ``_ATAJO_FALLBACK_PATH_MANAGER`` si otro plugin ya lo tiene, REQ-3): su
    callback importa el panel SOLO al click (D1), nunca al instalar. No crea
    paneles ni importa PySide (spec load-ui-menu + REQ-2). Devuelve True.
    """
    registrar_callbacks()
    menubar = nuke.menu("Nuke")
    saman = menubar.findItem(_NOMBRE_MENU)
    if saman is None:
        saman = menubar.addMenu(_NOMBRE_MENU)
    configuracion = saman.findItem(_NOMBRE_SUBMENU)
    if configuracion is None:
        configuracion = saman.addMenu(_NOMBRE_SUBMENU)
    if configuracion.findItem(_NOMBRE_ITEM_INFO) is None:
        configuracion.addCommand(_NOMBRE_ITEM_INFO, _mostrar_info_version)
    if saman.findItem(_NOMBRE_ITEM_PATH_MANAGER) is None:
        atajo = seleccionar_atajo(
            _ATAJO_PATH_MANAGER, _ATAJO_FALLBACK_PATH_MANAGER, _atajo_ocupado
        )
        saman.addCommand(_NOMBRE_ITEM_PATH_MANAGER, _abrir_path_manager, shortcut=atajo)
    return True


# Ejecucion cuando el bootstrap exec este archivo (y al importarlo): el target
# completa TODO el setup (callbacks + menu) al correr.
instalar()