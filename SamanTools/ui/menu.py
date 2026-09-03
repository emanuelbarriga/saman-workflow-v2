"""
SamanTools.ui.menu — target de ejecucion del bootstrap V2 (change load-contract, slice H4).

Este modulo es el archivo que ejecuta ``bootstrap/menu.py`` (``_cargar_menu_real``)
cuando el checkout esta completo: registra los callbacks del injector
(``registrar_callbacks``) exactamente UNA vez y construye el menu minimo
SamanTools. Es la capa ui del paquete y la UNICA que importa ``nuke`` a nivel
de modulo (0% coverage aceptado por diseno, ADR-7).

  - ``registrar_callbacks``: bind de ``nuke.addOnScriptLoad``/``addOnScriptSave``.
    En load resuelve la identidad ambiental (getpass/socket, permitido en la
    capa ui), detecta el SO (``core.entorno.detectar_so``), resuelve el store
    (``obtener_ruta_store``) y el perfil (``resolver_perfil``, con onboarding
    ficticio si no existe), arma el contexto desde ``nuke.root().name()``, aplica
    el override manual ``project_directory`` de la root (ADR-5) y decide por la
    cadena de precedencia (ADR-3: env pre-existente del render farm gana ->
    override manual gana -> env recien armado del perfil). Al final cachea y
    aplica el env (``cachear_env`` + ``aplicar_entorno``). En save re-afirma
    SOLO el env cacheado en memoria (ADR-2: nunca store, lock ni motor).
  - ``instalar``: registra los callbacks y construye el menu SamanTools >
    Configuracion con UN item de informacion de version; idempotente (no
    duplica items). Los botones de mantenimiento (Actualizar/Desinstalar) los
    agrega el PROPIO bootstrap despues, sobre el mismo submenu
    (``bootstrap/menu.py`` ``_agregar_boton_menu``).
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

    Orden: identidad -> store -> perfil (``resolver_perfil``, con onboarding a
    store ficticio si el par no existe) -> contexto del script
    (``nuke.root().name()``) -> override manual (knob ``project_directory``,
    ADR-5). Tolerante: cualquier fallo devuelve ``perfil=None`` y el flujo de
    carga no escribe nada.
    """
    try:
        usuario, hostname = _identidad_ambiental()
        ruta_store = injector.obtener_ruta_store()
        perfil = rutas_engine.resolver_perfil(usuario, hostname, ruta_store)
    except Exception:
        return None, None, ""
    ruta_plato = ""
    override = None
    try:
        root = nuke.root()
        if root is not None:
            ruta_plato = str(getattr(root, "name", lambda: "")() or "")
            override = injector._override_proyecto_desde_root(root)
    except Exception:
        pass
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


def instalar():
    """Construye el menu minimo SamanTools y registra los callbacks (idempotente).

    Reutiliza el menu/submenu si ya existen (patron V1): los botones de
    mantenimiento del bootstrap (Actualizar/Desinstalar) se agregan DESPUES
    sobre el mismo submenu Configuracion desde ``bootstrap/menu.py``. No crea
    paneles ni importa PySide (spec load-ui-menu). Devuelve True.
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
    return True


# Ejecucion cuando el bootstrap exec este archivo (y al importarlo): el target
# completa TODO el setup (callbacks + menu) al correr.
instalar()