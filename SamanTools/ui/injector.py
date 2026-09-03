"""
SamanTools.ui.injector - Capa de carga que inyecta el entorno de composicion
(change load-contract, slice H1 + perfil-por-usuario, slice S2).

Divide el trabajo en PURE / THIN:

  - ``armar_estado_env`` es PURA: ensambla el entorno TCL como datos
    (``PROJECT_ROOT`` + ``PYTHON_TO_VFX``/``PYTHON_COMP``/``PYTHON_FROM_VFX``)
    a partir de un perfil 3x3 (espacio → {OS → root}), SO explicito, ruta del
    plato y una base inyectable. NO importa nuke, NO muta ``os.environ`` ni
    ``__main__``. ``PROJECT_ROOT`` es el CORTE ESTRUCTURAL del plato
    (``raiz_proyecto_desde_ruta``); la base inyectada es SOLO fallback (nunca
    pisa un corte valido — el override del knob lo aplica ``_aplicar_precedencia``
    aparte, sobre el dict final); sin corte ni base cae a la root del perfil
    para el SO explicito (AD7). Las PYTHON_* SIEMPRE son las raices del perfil
    para el SO EXPLICITO (espacio faltante -> fallback hermano
    ``reconstruir_rutas`` del motor, AD7; irresoluble -> omitida, nunca "").
  - ``obtener_ruta_store(raiz_proyecto=None)`` resuelve la ruta del store de
    perfiles en cadena PROYECTO-PRIMERO (AD5/spec load-injector S2):
    ``{raiz_proyecto}/.saman/nuke_profiles.json`` -> ``NUKE_PROFILES_PATH``
    (env) -> ``SamanTools.config_local`` (modulo scoped gitignored, atributo o
    JSON hermano) -> ``~/.config/saman/nuke_profiles.json``. La raiz la calcula
    el CALLER (menu/panel) desde ``nuke.root().name()`` via
    ``raiz_proyecto_desde_ruta``; el store de proyecto GANA SIEMPRE que exista
    (probe anti-hang, AD6). Nunca un ``config_local.py`` en la raiz del
    repositorio (colision de nombres dentro de Nuke, spec load-injector).
  - ``_probe_store`` (R2/D6): verifica el dirname del store con
    ``entorno.estado_unidad`` (subprocess con timeout + cache ~10s: un mount
    SMB muerto devuelve ``conectado: False`` en vez de colgar) y SOLO si
    responde hace ``os.path.isfile``. JAMAS crea ``.saman/`` en lectura (nace
    lazy en la primera escritura bajo lock, en el motor).
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

from ..core import entorno
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
# Store local del proyecto (AD5): se resuelve bajo la raiz del proyecto.
_RUTA_STORE_PROYECTO_REL = os.path.join(".saman", "nuke_profiles.json")
# Orden canonico de espacios para el fallback de PROJECT_ROOT (AD7).
_ESPACIOS_INYECTOR = ("TO_VFX", "COMP", "FROM_VFX")


# --- Ensamblado puro -----------------------------------------------------------


def _raiz_fallback_so(perfil, espacio, so):
    """Root del perfil para ``so`` como ``PROJECT_ROOT`` degradado (AD7).

    Fallback FINAL de la cadena de ``PROJECT_ROOT`` (corte estructural ->
    base inyectada -> aqui), para scripts untitled o fuera de toda root sin
    base: usa la root del ESPACIO del contexto si existe para ``so``; si no,
    la PRIMERA root del perfil con plataforma ``so`` (orden canonico TO_VFX,
    COMP, FROM_VFX). Devuelve la root tal cual (spec S2: "current-SO space
    root"). Sin match -> ``None`` (y las PYTHON_* seguiran la cadena AD7
    del motor). Pura: no toca filesystem ni entorno.
    """
    if not isinstance(perfil, dict):
        return None
    if espacio:
        root = rutas_engine.ruta_para_espacio(perfil, espacio, so)
        if root:
            return str(root).replace("\\", "/").strip().rstrip("/")
    for espacio_c in _ESPACIOS_INYECTOR:
        root = rutas_engine.ruta_para_espacio(perfil, espacio_c, so)
        if root:
            return str(root).replace("\\", "/").strip().rstrip("/")
    return None


def armar_estado_env(perfil, so, ruta_plato, base=None):
    """Ensambla el entorno TCL como dict PURO (spec load-injector S2).

    ``perfil`` es 3x3 (espacio → {OS → root}). ``PROJECT_ROOT`` es el CORTE
    ESTRUCTURAL del plato (via ``get_context``); si el plato no produce corte
    (untitled o fuera de toda root) cae a la ``base`` inyectada y, si tampoco
    hay base, a la root del perfil para el SO explicito (``_raiz_fallback_so``,
    AD7). La base NUNCA pisa un corte valido: el override manual del knob
    ``project_directory`` se aplica aparte (``_aplicar_precedencia``) sobre el
    dict final. Las PYTHON_* SIEMPRE son las raices del perfil para el SO
    EXPLICITO (espacio faltante → fallback hermano ``reconstruir_rutas`` del
    motor; irresoluble → omitida, nunca ``""``). No muta ``os.environ`` ni
    ``__main__``; idem inputs -> idem outputs.
    """
    contexto = rutas_engine.get_context(perfil, ruta_plato)
    if not contexto.get("project_root"):
        if base is not None and str(base).strip():
            contexto["project_root"] = (
                str(base).replace("\\", "/").strip().rstrip("/") or None
            )
        else:
            contexto["project_root"] = _raiz_fallback_so(
                perfil, contexto.get("espacio"), so
            )
    # El SO explicito manda sobre el derivado del prefijo (spec S2).
    contexto["so"] = so
    return rutas_engine.variables_entorno(contexto, perfil=perfil)


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


def _probe_store(ruta):
    """Probe anti-hang de un store de proyecto (R2/D6): no cuelga, no crea nada.

    Verifica el DIRNAME del store (``{raiz}/.saman``) con
    ``entorno.estado_unidad`` — subprocess con timeout y cache ~10s a nivel de
    modulo: un mount SMB muerto devuelve ``conectado: False`` en vez de
    colgar — y SOLO si responde hace ``os.path.isfile(ruta)``. El cortocircuito
    garantiza que ``os.path.isfile`` (que tambien puede colgarse en un mount
    muerto) NUNCA corre sobre un dirname desconectado. ``estado_unidad`` solo
    hace ``ls -d``/``dir``: JAMAS crea ``.saman/`` en lectura (AD6 — el
    directorio nace lazy en la primera escritura bajo lock, en el motor).
    """
    if not ruta:
        return False
    padre = os.path.dirname(str(ruta)) or "."
    if not entorno.estado_unidad(padre)["conectado"]:
        return False
    return os.path.isfile(str(ruta))


def _probe_store_dir(directorio):
    """Probe anti-hang del DIRNAME del store (AD6, sin exigir el archivo).

    Usado por ``obtener_ruta_store`` cuando hay raiz de proyecto: el store del
    proyecto debe GANAR aunque ``nuke_profiles.json`` aun no exista (el
    onboarding lo crea ahi). Verifica que el directorio ``{raiz}/.saman``
    responda (``estado_unidad`` con timeout y cache ~10s — un mount muerto no
    cuelga). NO exige ``os.path.isfile``: ``estado_unidad`` solo hace ``ls -d``
    y nunca crea el directorio en lectura (nace lazy en la primera escritura
    del motor).
    """
    if not directorio:
        return False
    d = str(directorio).strip().rstrip("/\\")
    if not d:
        return False
    return entorno.estado_unidad(d)["conectado"]


def obtener_ruta_store(raiz_proyecto=None):
    """Resuelve la ruta del store de perfiles (spec load-injector S2, AD5).

    Cadena PROYECTO-PRIMERO: ``{raiz_proyecto}/.saman/nuke_profiles.json``
    (el store del proyecto GANA SIEMPRE que exista, probe anti-hang AD6) ->
    ``NUKE_PROFILES_PATH`` (env) -> ``SamanTools.config_local`` scoped ->
    ``~/.config/saman/nuke_profiles.json`` (default final; el onboarding
    persiste raices ficticias ahi). La ``raiz_proyecto`` la calcula el CALLER
    (menu/panel) desde ``nuke.root().name()`` via ``raiz_proyecto_desde_ruta``;
    sin raiz (untitled/fuera de toda root) la cadena arranca en el env. Nunca
    un modulo ``config_local`` en la raiz del repositorio.
    """
    if raiz_proyecto:
        raiz = str(raiz_proyecto).strip().rstrip("/\\")
        if raiz:
            ruta_proyecto = os.path.join(raiz, _RUTA_STORE_PROYECTO_REL)
            # El store del proyecto GANA aunque el .json no exista todavia:
            # si el dirname ({raiz}/.saman) responde (anti-hang AD6), el panel
            # debe apuntar aqui para que el onboarding LO CREE ahi — no caer
            # al home. _probe_store verifica el dirname y solo usa isfile
            # como confirmacion; un dirname conectado basta para elegirlo.
            if _probe_store_dir(os.path.dirname(ruta_proyecto)):
                return ruta_proyecto
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