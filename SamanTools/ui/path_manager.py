"""
SamanTools.ui.path_manager — helper PURO del panel Path Manager (Ctrl+Alt+R),
contrato usuario-solo (cambio perfil-por-usuario, S1: migracion del slice P1).

Divide el trabajo en capa pura / widget fino (precedente del injector):
este modulo es 100% puro — NO importa nuke ni PySide, NO lee ni muta
``os.environ`` y recibe identidad (``usuario``), SO y ruta del store como
parametros inyectados. Devuelve DATOS; el widget (P2) renderiza y aplica el
env via ``injector.cachear_env`` + ``aplicar_entorno``. El hostname y la
escalera de precedencia (par exacto → default → host ajeno) DESAPARECEN
(AD2): un perfil pertenece al usuario, con raices independientes por espacio
y por SO (3x3).

  - ``estado_panel(ruta_store, usuario, so)``: corte de LECTURA — perfil
    activo (3x3), raiz del SO actual (primera raiz no-None del perfil para el
    SO, orden canonico de espacios), estado de unidad y marcador de
    desconocido/legacy. Nunca escribe.
  - ``detectar_desconocido(ruta_store, usuario)``: deteccion SOLO-LECTURA
    sobre ``leer_perfiles``: el usuario tiene forma nueva → ``False``; si no
    (ausente, legacy o store corrupto) → ``True``. NUNCA llama a
    ``resolver_perfil`` (que haria onboarding) y NUNCA escribe (AD2).
  - ``preparar_cambio_base(usuario, ruta_store, so, nueva_base,
    ruta_plato="")``: corte de ESCRITURA (REQ-4, D7) — READ-MERGE-WRITE bajo
    el lock de ``guardar_perfiles``: la nueva base (raiz de proyecto) rellena
    el slot del SO en los TRES espacios (``{base}/{ESPACIO}``); otras raices
    del perfil y otros usuarios quedan intactos. Devuelve
    ``{"perfil", "env", "unidad"}`` como datos. Sin perfil nuevo → ValueError
    claro (nunca onboarding silencioso).
  - ``preparar_onboarding(usuario, ruta_store, base, so, ruta_plato="")``:
    corte de ESCRITURA (REQ-5, D3) — persiste el perfil via ``asegurar_perfil``
    (lock-safe, slotting de la base inyectada) y devuelve
    ``{"perfil", "env", "unidad"}`` como datos.

Determinismo: inputs identicos → salidas identicas (el unico dato vivo,
``entorno.estado_unidad``, respeta timeout + cache del motor). Ninguna ruta
real del estudio: solo raices ficticias (``/Volumes/estudio/2026``,
``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

from ..core import entorno
from ..core import rutas_engine
from . import injector

# Orden canonico de los tres espacios (mismo del motor).
_ESPACIOS = ("TO_VFX", "COMP", "FROM_VFX")


def _raiz_para_so(perfil, so):
    """Primera raiz NO-None del perfil para el ``so`` (orden canonico).

    Con un perfil 3x3 no hay una unica "base": la raiz del SO actual es la
    del primer espacio que la tenga (nunca lanza; ``None`` si el SO no esta).
    """
    if not isinstance(perfil, dict):
        return None
    for espacio in _ESPACIOS:
        root = rutas_engine.ruta_para_espacio(perfil, espacio, so)
        if root:
            return root
    return None


def _primera_candidata(so):
    """Primera candidata de ``entorno.rutas_base(so)`` o ``None`` si no hay."""
    candidatas = entorno.rutas_base(so)
    return candidatas[0] if candidatas else None


def _normalizar_base(base):
    """Normaliza la base inyectada: ``\\`` → ``/``, sin espacios ni ``/`` final.

    Convencion del motor (``absolutizar``): forward slashes SIEMPRE. Una base
    vacia tras normalizar es un error del caller.
    """
    normalizada = str(base).replace("\\", "/").strip().rstrip("/")
    if not normalizada:
        raise ValueError("La base no puede estar vacia")
    return normalizada


# --- Corte de lectura --------------------------------------------------------


def estado_panel(ruta_store, usuario, so):
    """Estado de lectura del panel (REQ-1/REQ-2/REQ-3). Puro; sin escrituras.

    Devuelve ``{"conocido", "perfil", "base_actual", "unidad"}``:

    * ``conocido`` — ``True`` si el usuario tiene un perfil con forma NUEVA
      (3x3); ``False`` si es desconocido o legacy (marcador de onboarding,
      AD2). Nunca escribe.
    * ``perfil`` — dict 3x3 del usuario, o ``None``.
    * ``base_actual`` — primera raiz del perfil para el ``so`` inyectado, o
      ``None``.
    * ``unidad`` — ``entorno.estado_unidad(base_actual)`` (perfil conocido) o
      de la primera candidata de ``entorno.rutas_base(so)`` (sin perfil);
      timeout + cache respetados, nunca se cuelga en un mount muerto.
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        return {
            "conocido": False,
            "perfil": None,
            "base_actual": None,
            "unidad": entorno.estado_unidad(_primera_candidata(so)),
        }
    base_actual = _raiz_para_so(perfil, so)
    return {
        "conocido": True,
        "perfil": perfil,
        "base_actual": base_actual,
        "unidad": entorno.estado_unidad(base_actual),
    }


def detectar_desconocido(ruta_store, usuario):
    """``True`` si el usuario no tiene perfil con forma nueva; ``False`` si lo tiene.

    Lectura pura (AD2): replica sobre ``leer_perfiles``; una entrada legacy
    cuenta como desconocida (la escritura la regenerara). NUNCA escribe y
    NUNCA llama a ``resolver_perfil`` (que haria onboarding automatico).
    Store ausente o corrupto → ``True`` (no confirmable). Sin raise.
    """
    try:
        perfiles = rutas_engine.leer_perfiles(ruta_store)
    except ValueError:
        return True
    return rutas_engine.detectar_forma_perfil(perfiles.get(usuario)) != "nuevo"


# --- Corte de escritura: cambio de base (REQ-4, D7) ---------------------------


def preparar_cambio_base(usuario, ruta_store, so, nueva_base, ruta_plato=""):
    """Persiste la nueva base del slot SO del perfil y devuelve DATA (REQ-4, D7).

    READ-MERGE-WRITE bajo el lock de ``guardar_perfiles``: la ``nueva_base``
    es una raiz de proyecto; rellena el slot del SO en los TRES espacios
    (``{base}/{ESPACIO}``) y conserva las otras raices del perfil y los demas
    usuarios. Devuelve ``{"perfil", "env", "unidad"}``: el perfil actualizado,
    el env delta de ``injector.armar_estado_env`` (con la base nueva forzada)
    y el estado de unidad de la base nueva. NO toca ``os.environ``: la
    propagacion la hace el widget (P2). Sin perfil nuevo → ``ValueError``
    claro (nunca onboarding silencioso como ``resolver_perfil``).
    """
    base_norm = _normalizar_base(nueva_base)
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    perfil_nuevo = rutas_engine.crear_perfil_default(base=base_norm)
    # Solo el slot del SO entrante: conserva los demas SO y espacios ajenos.
    actualizado = {}
    for espacio in _ESPACIOS:
        raices = dict(perfil.get(espacio) or {})
        raices[so] = perfil_nuevo[espacio][so]
        actualizado[espacio] = raices
    rutas_engine.guardar_perfiles(ruta_store, {usuario: actualizado})
    env = injector.armar_estado_env(actualizado, so, ruta_plato, base=base_norm)
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(base_norm),
    }


# --- Corte de escritura: onboarding (REQ-5, D3) -------------------------------


def preparar_onboarding(usuario, ruta_store, base, so, ruta_plato=""):
    """Persiste el onboarding del usuario y devuelve DATA (REQ-5, D3).

    Via ``asegurar_perfil`` (lock-safe): construye el perfil 3x3 con raices
    ficticias por espacio y plataforma y slotting de la base inyectada
    (``crear_perfil_default``: ``/Volumes/`` → macOS, ``^[A-Za-z]:`` →
    Windows, ``/mnt/`` → Linux); si otro proceso gano la carrera devuelve el
    perfil del ganador sin reescribir. Devuelve ``{"perfil", "env",
    "unidad"}``: el perfil persistido, el env delta de
    ``injector.armar_estado_env`` (con la base como PROJECT_ROOT) y el estado
    de unidad de esa base. NO toca ``os.environ``.
    """
    base_norm = _normalizar_base(base)
    perfil = rutas_engine.asegurar_perfil(usuario, ruta_store, base=base_norm)
    env = injector.armar_estado_env(perfil, so, ruta_plato, base=base_norm)
    return {
        "perfil": perfil,
        "env": env,
        "unidad": entorno.estado_unidad(base_norm),
    }