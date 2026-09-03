"""
SamanTools.ui.injector - Capa de carga que inyecta el entorno de composicion
(change load-contract, slice H1).

Divide el trabajo en PURE / THIN:

  - ``armar_estado_env`` es PURA: ensambla el entorno TCL como datos
    (``PROJECT_ROOT`` + ``PYTHON_TO_VFX``/``PYTHON_COMP``/``PYTHON_FROM_VFX``)
    a partir de un perfil 3x3 (espacio → {OS → root}), SO explicito, ruta del
    plato y una base inyectable. NO importa nuke, NO muta ``os.environ`` ni
    ``__main__``: corrige el gap del motor (issue #2286) donde un script
    untitled o fuera de toda root no produce corte estructural, usando la
    base del parametro como ``PROJECT_ROOT``.
  - ``obtener_ruta_store`` resuelve la ruta del store de perfiles en cadena:
    ``NUKE_PROFILES_PATH`` (env) -> ``SamanTools.config_local`` (modulo scoped
    gitignored, atributo o JSON hermano) -> ``~/.config/saman/nuke_profiles.json``.
    Nunca un ``config_local.py`` en la raiz del repositorio (colision de
    nombres dentro de Nuke, spec load-injector).
  - ``aplicar_entorno`` es THIN e idempotente: vuelca el dict en
    ``os.environ`` y en ``__main__.__dict__`` (para que el TCL
    ``[getenv PROJECT_ROOT]`` evalua en nodos Read/Write).
  - ``_override_proyecto_desde_root`` es PURA: detecta el knob
    ``project_directory`` de la root (ADR-5) y normaliza su valor a forward
    slashes; vacio/ausente -> ``None``.
  - ``_aplicar_precedencia`` (PURA) y ``cachear_env`` implementan la
    maquinaria de precedencia + cache en memoria (ADR-2/ADR-3): el env ya
    presente en el entorno ANTES de que el loader escriba (render farm)
    gana y se omite la escritura; el override manual gana sobre el perfil;
    ``cachear_env`` registra que el env fue inyectado (``_env_inyectado``)
    y lo deja en ``_env_cache`` para que el save re-afirme SOLO desde
    memoria (sin disco ni lock).

``registrar_callbacks`` (bind de nuke.ui, addOnScriptLoad/addOnScriptSave) se
implementa en ``ui/menu.py`` (H4), que necesita el modulo nuke en el momento
de la llamada; aqui solo vive su flag de idempotencia
(``_callbacks_registrados``), cacheado por sys.modules entre re-ejecuciones
del bootstrap. Ninguna ruta real del estudio: solo raices ficticias
(``/Volumes/estudio/2026``, ``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

import json
import os

from ..core import rutas_engine

# Cache en memoria del ultimo env inyectado (ADR-2: el save re-afirma desde
# memoria, sin store ni lock) y flag de inyeccion (ADR-3: el shim respeta
# el env que el injector ya escribio esta sesion).
_env_cache = None
_env_inyectado = False

# Flag de idempotencia de registrar_callbacks (ADR-7): vive AQUI, no en
# ui/menu.py, porque sys.modules cachea este modulo entre re-ejecuciones del
# bootstrap (cada exec de menu.py recibe un namespace fresco). El propio bind
# de nuke.ui (addOnScriptLoad/addOnScriptSave) se implementa en menu.py (H4).
_callbacks_registrados = False

_CLAVE_PROJECT_ROOT = "PROJECT_ROOT"
_NOMBRE_KNOB_OVERRIDE = "project_directory"
_RUTA_STORE_HOME = os.path.join(".config", "saman", "nuke_profiles.json")


# --- Ensamblado puro -----------------------------------------------------------


def armar_estado_env(perfil, so, ruta_plato, base=None):
    """Ensambla el entorno TCL como dict PURO (spec load-injector, perfil-por-usuario).

    ``perfil`` es 3x3 (espacio → {OS → root}). La raiz de proyecto es el
    CORTE ESTRUCTURAL del plato (``raiz_proyecto_desde_ruta``); si se inyecta
    ``base`` (override manual del knob ``project_directory``, ADR-5), esa base
    GANA al corte como ``PROJECT_ROOT``; el SO se fuerza al inyectado si el
    contexto no lo resolvio (scripts untitled o fuera de toda root). Con
    ``base`` inyectada el proyecto manda sobre las raices del perfil (AD7):
    las PYTHON_* se derivan del hermano ``reconstruir_rutas`` de la raiz
    resuelta. Sin ``base``, las PYTHON_* son las raices del perfil para el SO.
    No muta ``os.environ`` ni ``__main__``; idem inputs -> idem outputs.
    """
    contexto = rutas_engine.get_context(perfil, ruta_plato)
    if base is not None:
        # La base inyectada es un override (knob project_directory): GANA al
        # corte estructural (ADR-3/ADR-5), igual que en el contrato V1.
        contexto["project_root"] = base
    if not contexto.get("so"):
        contexto["so"] = so
    perfil_para_env = None if base is not None else perfil
    return rutas_engine.variables_entorno(contexto, perfil=perfil_para_env)


# --- Resolucion del store de perfiles ------------------------------------------


def _leer_config_local():
    """Devuelve el store de ``SamanTools.config_local`` (scoped) o ``None``.

    Tolerante (ADR-6): import fallido o sin valor -> ``None``. El valor sale
    del atributo ``NUKE_PROFILES_PATH`` del modulo o, si el modulo existe sin
    atributo, del JSON hermano ``config_local.json`` junto al propio modulo
    (ambos gitignored, nunca en la raiz del repo).
    """
    try:
        from .. import config_local as _modulo
    except ImportError:
        return None
    if _modulo is None:
        return None

    valor = getattr(_modulo, "NUKE_PROFILES_PATH", None)
    if valor and str(valor).strip():
        return str(valor)

    directorio = os.path.dirname(os.path.abspath(getattr(_modulo, "__file__", "")))
    if not directorio:
        return None
    ruta_json = os.path.join(directorio, "config_local.json")
    try:
        with open(ruta_json, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(datos, dict):
        valor = datos.get("NUKE_PROFILES_PATH")
        if valor and str(valor).strip():
            return str(valor)
    return None


def obtener_ruta_store():
    """Resuelve la ruta del store de perfiles (spec load-injector, ADR-6).

    Cadena: ``NUKE_PROFILES_PATH`` (env) -> ``SamanTools.config_local``
    scoped -> ``~/.config/saman/nuke_profiles.json`` (default final; el
    onboarding persiste raices ficticias ahi). Nunca un modulo
    ``config_local`` en la raiz del repositorio.
    """
    desde_env = os.environ.get("NUKE_PROFILES_PATH")
    if desde_env and str(desde_env).strip():
        return str(desde_env)

    desde_config = _leer_config_local()
    if desde_config:
        return desde_config

    return os.path.join(os.path.expanduser("~"), _RUTA_STORE_HOME)


# --- Aplicacion fina e idempotente ---------------------------------------------


def aplicar_entorno(env):
    """Vuelca ``env`` en ``os.environ`` y en ``__main__.__dict__`` (THIN).

    Idempotente: repetir el mismo dict no duplica ni altera valores. El
    import de ``__main__`` es diferido para que importar este modulo no
    tenga efectos laterales.
    """
    if not isinstance(env, dict) or not env:
        return
    normalizado = {k: str(v) for k, v in env.items() if v is not None}
    if not normalizado:
        return
    os.environ.update(normalizado)
    import __main__

    __main__.__dict__.update(normalizado)


# --- Precedencia y cache en memoria (ADR-2/ADR-3) ------------------------------


def _override_proyecto_desde_root(root):
    """Detecta el override manual ``project_directory`` de la root (ADR-5).

    PURA y fake-root testeable: declarado iff la root expone el knob
    ``project_directory`` y su ``value()`` es un string no vacio; la base es
    el valor normalizado a forward slashes. Vacio/blanco/ausente/root sin
    ``knobs()`` -> ``None``.
    """
    if root is None:
        return None
    obtener_knobs = getattr(root, "knobs", None)
    if not callable(obtener_knobs):
        return None
    tabla = obtener_knobs()
    if not isinstance(tabla, dict):
        return None
    knob = tabla.get(_NOMBRE_KNOB_OVERRIDE)
    if knob is None:
        return None
    valor = getattr(knob, "value", None)
    if not callable(valor):
        return None
    texto = valor()
    if not isinstance(texto, str) or not texto.strip():
        return None
    return texto.replace("\\", "/").strip()


def _aplicar_precedencia(env, root_override, env_preexistente):
    """Decide que env gana segun la cadena de precedencia (ADR-3).

    PURA, devuelve el dict a aplicar o ``None`` (no escribir nada):

      1. render farm/headless: si ``env_preexistente`` (snapshot del entorno
         ANTES de que el loader escriba) ya trae ``PROJECT_ROOT``, gana ese
         env y la escritura es no-op -> ``None``.
      2. override manual: si ``root_override`` no esta vacio, gana la base
         override: se fuerza ``PROJECT_ROOT`` al override normalizado
         conservando el resto de variables del env ensamblado.
      3. perfil: el env ensamblado tal cual.
    """
    preexistente = env_preexistente or {}
    if str(preexistente.get(_CLAVE_PROJECT_ROOT) or "").strip():
        return None
    if root_override:
        if isinstance(env, dict):
            base_override = {
                _CLAVE_PROJECT_ROOT: str(root_override)
                .replace("\\", "/")
                .strip()
            }
            return dict(env, **base_override)
        return {_CLAVE_PROJECT_ROOT: str(root_override).replace("\\", "/").strip()}
    return env if isinstance(env, dict) else {}


def cachear_env(env):
    """Registra el env como inyectado: lo cachea y marca ``_env_inyectado``.

    El save (ADR-2) re-afirma SOLO este dict en memoria: ni store, ni lock,
    ni funciones del motor en la ruta de guardado.
    """
    global _env_cache, _env_inyectado
    _env_cache = dict(env) if isinstance(env, dict) else {}
    _env_inyectado = True