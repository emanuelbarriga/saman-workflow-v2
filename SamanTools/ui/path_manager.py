"""
SamanTools.ui.path_manager — helper PURO del panel Path Manager (Ctrl+Alt+R),
contrato usuario-solo (cambio perfil-por-usuario, S3: helper slice).

Divide el trabajo en capa pura / widget fino (precedente del injector):
este modulo es 100% puro — NO importa nuke ni PySide, NO lee ni muta
``os.environ`` y recibe identidad (``usuario``), SO y ruta del store como
parametros inyectados. Devuelve DATOS; el widget (S4) renderiza y aplica el
env via ``injector.cachear_env`` + ``aplicar_entorno``. El hostname y la
escalera de precedencia (par exacto → default → host ajeno) DESAPARECEN
(AD2): un perfil pertenece al usuario, con raices independientes por espacio
y por SO (3x3).

  - ``listar_perfiles(ruta_store)`` (S3): usuarios del store, ordenados
    alfabeticamente; store ausente o corrupto → ``[]`` sin lanzar.
  - ``estado_panel(ruta_store, usuario, so)``: corte de LECTURA — perfil
    activo (3x3), raiz del SO actual (primera raiz no-None del perfil para el
    SO, orden canonico de espacios), estado de unidad y marcador de
    desconocido/legacy. El flag ``legacy`` (S3) reporta una entrada con forma
    VIEJA (``hosts``/``default``) SOLO-LECTURA: el helper NUNCA la reescribe
    al detectar — el widget avisa y la regeneracion ocurre en la siguiente
    escritura del motor (AD1).
  - ``preparar_seleccion_perfil(usuario, ruta_store, so, ruta_plato="")``
    (S3): perfil + env + unidad de un usuario EXISTENTE, sin escribir nunca.
    Usuario inexistente o legacy → ``ValueError`` claro (la seleccion no es
    creacion; nunca onboarding automatico). La unidad se consulta sobre la
    raiz del SO actual del perfil.
  - ``detectar_desconocido(ruta_store, usuario)``: deteccion SOLO-LECTURA
    sobre ``leer_perfiles``: el usuario tiene forma nueva → ``False``; si no
    (ausente, legacy o store corrupto) → ``True``. NUNCA llama a
    ``resolver_perfil`` (que haria onboarding) y NUNCA escribe (AD2).
  - ``preparar_cambio_base(usuario, ruta_store, so, espacio, nueva_ruta,
    ruta_plato="")``: corte de ESCRITURA POR ESPACIO (spec S3, D7) —
    READ-MERGE-WRITE bajo el lock de ``guardar_perfiles``: SOLO se reemplaza
    el slot ``(espacio, so)`` (los espacios son independientes); los otros
    espacios, otros SO y otros usuarios quedan intactos. Un ``espacio`` que
    no es un nombre canonico pero PARECE una ruta se interpreta como el modo
    TODOS (contrato transitorio del widget P2, migrado en S4): es una base de
    proyecto y rellena el slot del SO en los tres espacios
    (``{base}/{ESPACIO}``). Un valor que no es ni espacio ni ruta →
    ``ValueError``. Sin perfil nuevo → ``ValueError`` claro (nunca onboarding
    silencioso). Devuelve ``{"perfil", "env", "unidad"}`` como datos.
  - ``preparar_onboarding(usuario, ruta_store, base, so, ruta_plato="")``:
    corte de ESCRITURA (REQ-5, D3) — persiste el perfil via ``asegurar_perfil``
    (lock-safe, slotting de la base inyectada) y devuelve
    ``{"perfil", "env", "unidad"}`` como datos.

Determinismo: inputs identicos → salidas identicas (el unico dato vivo,
``entorno.estado_unidad``, respeta timeout + cache del motor). Ninguna ruta
real del estudio: solo raices ficticias (``/Volumes/estudio/2026``,
``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

import re

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


def _normalizar_ruta(ruta):
    """Normaliza la ruta inyectada: ``\\`` → ``/``, sin espacios ni ``/`` final.

    Convencion del motor (``absolutizar``): forward slashes SIEMPRE. Una ruta
    vacia tras normalizar es un error del caller.
    """
    normalizada = str(ruta).replace("\\", "/").strip().rstrip("/")
    if not normalizada:
        raise ValueError("La ruta no puede estar vacia")
    return normalizada


def _es_ruta_aparente(valor):
    """``True`` si el valor parece una ruta de base (contiene ``/`` o drive).

    Distingue el modo TODOS (una base de proyecto: ``/Volumes/estudio/2027``,
    ``L:/VFX/2027``) de un nombre de espacio invalido (``OTRO``) en
    ``preparar_cambio_base``, evitando reescrituras silenciosas por typos.
    """
    texto = str(valor)
    return "/" in texto or bool(re.match(r"^[A-Za-z]:", texto))


def _copia_con_slot(perfil, so, slots):
    """Copia del perfil con SOLO los slots indicados reemplazados.

    ``slots`` es ``{espacio: raiz}``; para cada espacio canonico conserva las
    raices existentes (otros SO intactos) y, si el espacio esta en ``slots``,
    reemplaza la raiz del ``so``. Los demas espacios quedan tal cual.
    """
    actualizado = {}
    for espacio in _ESPACIOS:
        raices = dict(perfil.get(espacio) or {})
        if espacio in slots:
            raices[so] = slots[espacio]
        actualizado[espacio] = raices
    return actualizado


# --- Corte de lectura --------------------------------------------------------


def listar_perfiles(ruta_store):
    """Usuarios del store, ordenados alfabeticamente (spec S3, orden estable).

    Store ausente o corrupto → ``[]`` sin lanzar (la UI degrada al combo
    vacio). Puro: solo ``leer_perfiles``; nunca escribe ni crea ``.saman/``.
    """
    try:
        perfiles = rutas_engine.leer_perfiles(ruta_store)
    except ValueError:
        return []
    return sorted(perfiles)


def estado_panel(ruta_store, usuario, so):
    """Estado de lectura del panel (REQ-1/REQ-2/REQ-3). Puro; sin escrituras.

    Devuelve ``{"conocido", "perfil", "base_actual", "legacy", "unidad"}``:

    * ``conocido`` — ``True`` si el usuario tiene un perfil con forma NUEVA
      (3x3); ``False`` si es desconocido o legacy (marcador de onboarding,
      AD2). Nunca escribe.
    * ``perfil`` — dict 3x3 del usuario, o ``None``.
    * ``base_actual`` — primera raiz del perfil para el ``so`` inyectado, o
      ``None``.
    * ``legacy`` — ``True`` SOLO si el usuario tiene una entrada con forma
      VIEJA (``hosts``/``default``, sin espacios): flag de regeneracion
      SOLO-LECTURA (spec S3) — el helper no reescribe; la regeneracion
      ocurre en la siguiente escritura del motor (AD1). Usuario ausente o
      perfil nuevo → ``False``.
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
            "legacy": perfil is not None,
            "unidad": entorno.estado_unidad(_primera_candidata(so)),
        }
    base_actual = _raiz_para_so(perfil, so)
    return {
        "conocido": True,
        "perfil": perfil,
        "base_actual": base_actual,
        "legacy": False,
        "unidad": entorno.estado_unidad(base_actual),
    }


def preparar_seleccion_perfil(usuario, ruta_store, so, ruta_plato=""):
    """Perfil + env + unidad de un usuario EXISTENTE (spec S3).

    Lectura pura del store → ``perfiles.get(usuario)`` → env
    (``injector.armar_estado_env``) → ``entorno.estado_unidad`` sobre la raiz
    del SO actual (primera raiz no-None, orden canonico de espacios). Usuario
    inexistente O con forma legacy → ``ValueError`` claro: la seleccion no es
    creacion (a diferencia de ``resolver_perfil``, NUNCA hace onboarding) y
    NUNCA escribe. Devuelve ``{"perfil", "env", "unidad"}`` y NO toca
    ``os.environ``.
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': la seleccion no crea perfiles"
        )
    env = injector.armar_estado_env(perfil, so, ruta_plato)
    base_actual = _raiz_para_so(perfil, so)
    return {
        "perfil": perfil,
        "env": env,
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


# --- Corte de escritura: cambio de base por espacio (REQ-4, D7/S3) ------------


def preparar_cambio_base(usuario, ruta_store, so, espacio, nueva_ruta="", ruta_plato=""):
    """Persiste la nueva raiz del slot ``(espacio, so)`` y devuelve DATA (S3).

    READ-MERGE-WRITE bajo el lock de ``guardar_perfiles``: los espacios son
    INDEPENDIENTES (AD1) y solo cambia el slot del ``espacio`` y ``so``
    entrantes; las otras raices del perfil (otros espacios, otros SO) y los
    demas usuarios quedan intactos.

    Dos modos:

    * Por espacio (spec S3): ``espacio`` es un espacio canonico
      (TO_VFX|COMP|FROM_VFX) y ``nueva_ruta`` su raiz completa; SOLO ese slot
      se reemplaza. El env delta sale de ``armar_estado_env`` (PROJECT_ROOT
      por corte estructural del plato) y la unidad se consulta sobre la raiz
      nueva.
    * Todos (compat transitoria con el widget P2, migrado en S4): ``espacio``
      no es canonico pero PARECE una base de proyecto (``/Volumes/...``,
      ``L:/...``); la base rellena el slot del SO en los TRES espacios como
      ``{base}/{ESPACIO}`` (``crear_perfil_default``), con env forzado a esa
      base y unidad sobre ella.

    Un ``espacio`` que no es ni canonico ni ruta → ``ValueError``. Sin perfil
    nuevo → ``ValueError`` claro (nunca onboarding silencioso como
    ``resolver_perfil``). Devuelve ``{"perfil", "env", "unidad"}`` y NO toca
    ``os.environ``: la propagacion la hace el widget (S4).
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    if espacio in _ESPACIOS:
        raiz_nueva = _normalizar_ruta(nueva_ruta)
        slots = {espacio: raiz_nueva}
        base_env = None
    elif _es_ruta_aparente(espacio):
        raiz_nueva = _normalizar_ruta(espacio)
        perfil_slot = rutas_engine.crear_perfil_default(base=raiz_nueva)
        slots = {esp: perfil_slot[esp][so] for esp in _ESPACIOS}
        base_env = raiz_nueva
    else:
        raise ValueError(
            f"Espacio invalido para cambio de base: '{espacio}' "
            f"(esperado {', '.join(_ESPACIOS)} o una base de proyecto)"
        )
    actualizado = _copia_con_slot(perfil, so, slots)
    rutas_engine.guardar_perfiles(ruta_store, {usuario: actualizado})
    env = injector.armar_estado_env(actualizado, so, ruta_plato, base=base_env)
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(raiz_nueva),
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
    base_norm = _normalizar_ruta(base)
    perfil = rutas_engine.asegurar_perfil(usuario, ruta_store, base=base_norm)
    env = injector.armar_estado_env(perfil, so, ruta_plato, base=base_norm)
    return {
        "perfil": perfil,
        "env": env,
        "unidad": entorno.estado_unidad(base_norm),
    }