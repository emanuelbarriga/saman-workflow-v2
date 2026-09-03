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
  - ``raices_para_so(usuario, ruta_store, so)``: lectura pura — las TRES
    raices del perfil para el ``so`` inyectado como ``{espacio: raiz}``
    (para que el widget renderice los campos del modo avanzado); usuario sin
    perfil nuevo o store ausente/corrupto → ``{}`` sin lanzar.
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
  - ``guardar_base_unificada(usuario, ruta_store, so, base="",
    ruta_plato="")``: corte de ESCRITURA del modo SIMPLE del widget
    (mockup): UNA base de proyecto rellena el slot ``(espacio, so)`` de los
    TRES espacios como ``{base}/{ESPACIO}`` (misma regla que el modo TODOS
    de ``preparar_cambio_base``, sin tocar otros SO ni otros usuarios).
    Base vacia o sin perfil nuevo → ``ValueError`` claro. Devuelve
    ``{"perfil", "env", "unidad"}`` como datos.
  - ``preparar_onboarding(usuario, ruta_store, base, so, ruta_plato="")``:
    corte de ESCRITURA (REQ-5, D3) — persiste el perfil via ``asegurar_perfil``
    (lock-safe, slotting de la base inyectada) y devuelve
    ``{"perfil", "env", "unidad"}`` como datos.
  - ``onboarding_perfil(nombre, ruta_store, base, so, ruta_plato="",
    seleccion_path=None)`` (S5): wrapper que encadena ``preparar_onboarding``
    con un NOMBRE LIBRE y ``guardar_seleccion`` — crea el perfil y deja la
    seleccion activa guardada por estacion.
  - ``cargar_seleccion(ruta_store, seleccion_path=None)`` (S5): perfil activo
    guardado EN LA ESTACION (``~/.config/saman/seleccion.json``,
    ``{"stores": {ruta_store: nombre}}``) o ``None``. Ausente/corrupto/sin
    entrada para el store → ``None`` sin lanzar.
  - ``guardar_seleccion(ruta_store, nombre, seleccion_path=None)`` (S5):
    persiste la seleccion activa de ``ruta_store`` con merge (otros stores
    intactos) y escritura atomica (tmp + ``os.replace``); devuelve ``bool``.
  - ``renombrar_perfil(ruta_store, nombre_viejo, nombre_nuevo)`` (S5): re-key
    de un perfil conservando las 9 raices (TO_VFX/COMP/FROM_VFX x 3 SO) con
    READ-RENAME-WRITE bajo el lock del motor; ``ValueError`` claro si el viejo
    no existe o el nuevo ya esta tomado. Devuelve el store interno actualizado.
  - Espacios EXTRA (spec panel-helper, espacios-extra): claves del perfil
    fuera de ``_ESPACIOS``, guardadas bajo su nombre sanitizado (UPPER,
    ``A-Z0-9``, espacio→``_``, colapso). ``sanitizar_espacio_extra`` valida el
    nombre (delega la sanitizacion a ``rutas_engine._clave_env_para_espacio``
    y rechaza: colision canonica, ``hosts``/``default``, ``PROJECT_ROOT``,
    duplicado intra-extra y nombres path-like/JSON-reservados);
    ``raices_para_so`` y el env los listan canonico-primero + SORTED (D3);
    ``preparar_cambio_base`` acepta un extra conocido del perfil (slot
    ``(extra, so)``); ``agregar_espacio_extra``/``eliminar_espacio_extra``
    persisten/quitan extras bajo el lock del motor. R3: la forma del perfil
    sigue siendo SOLO canonica (``detectar_forma_perfil`` del motor) — una
    entrada manuscrita con extras pero SIN espacio canonico se clasifica
    legacy (``estado_panel.legacy``, SOLO-LECTURA) y la siguiente escritura
    la regenera entera (extras perdidos); el helper NUNCA emite ese store por
    sus flujos: todo corte de escritura exige forma nueva (nunca extras-only).

Determinismo: inputs identicos → salidas identicas (el unico dato vivo,
``entorno.estado_unidad``, respeta timeout + cache del motor). Ninguna ruta
real del estudio: solo raices ficticias (``/Volumes/estudio/2026``,
``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

import json
import os
import re
import tempfile

from ..core import entorno
from ..core import rutas_engine
from . import injector

# Orden canonico de los tres espacios (mismo del motor).
_ESPACIOS = ("TO_VFX", "COMP", "FROM_VFX")

# Seleccion activa POR ESTACION (local): nunca viaja en el store del
# proyecto, vive en ~/.config/saman/seleccion.json (parametrizable para tests).
_RUTA_SELECCION_DEFAULT = os.path.join("~", ".config", "saman", "seleccion.json")


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

    ``slots`` es ``{espacio: raiz}``; para cada espacio conserva las raices
    existentes (otros SO intactos) y, si el espacio esta en ``slots``,
    reemplaza la raiz del ``so``. Los demas espacios quedan tal cual. D5:
    se iteran TODAS las claves del perfil (canonicos en orden ``_ESPACIOS`` +
    extras SORTED, D3), no solo los canonicos — asi los espacios EXTRA y sus
    raices de otros SO sobreviven a cualquier cambio de base.
    """
    claves = list(_ESPACIOS) + sorted(
        clave for clave in perfil if clave not in _ESPACIOS
    )
    actualizado = {}
    for espacio in claves:
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


def raices_para_so(usuario, ruta_store, so):
    """Raices de los espacios del usuario para el ``so`` (lectura pura).

    Relee el store y devuelve ``{espacio: raiz}`` con la raiz del ``so``
    inyectado para cada espacio (raices ausentes → ``None``): los canonicos
    primero en orden ``_ESPACIOS`` y luego los extras SORTED lexicograficamente
    (D3, determinista). Es el dato de lectura que el widget usa para renderizar
    los campos del modo avanzado (mockup) con las rutas ACTUALES del perfil.
    Usuario sin perfil nuevo, store ausente o corrupto → ``{}`` sin lanzar.
    Nunca escribe ni toca ``os.environ``.
    """
    try:
        perfiles = rutas_engine.leer_perfiles(ruta_store)
    except ValueError:
        return {}
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        return {}
    extras = sorted(clave for clave in perfil if clave not in _ESPACIOS)
    return {
        espacio: rutas_engine.ruta_para_espacio(perfil, espacio, so)
        for espacio in list(_ESPACIOS) + extras
    }


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

    Dos modos y un extra conocido:

    * Por espacio (spec S3): ``espacio`` es un espacio canonico
      (TO_VFX|COMP|FROM_VFX) y ``nueva_ruta`` su raiz completa; SOLO ese slot
      se reemplaza. El env delta sale de ``armar_estado_env`` (PROJECT_ROOT
      por corte estructural del plato) y la unidad se consulta sobre la raiz
      nueva.
    * Extra del perfil (spec panel-helper, R4): ``espacio`` es una clave
      EXISTENTE del perfil fuera de ``_ESPACIOS`` (p.ej. ``3D``); SOLO el
      slot ``(extra, so)`` se reemplaza y el env delta lleva ``PYTHON_<extra>``
      con la raiz nueva.
    * Todos (compat transitoria con el widget P2, migrado en S4): ``espacio``
      no es canonico ni clave del perfil pero PARECE una base de proyecto
      (``/Volumes/...``, ``L:/...``); la base rellena el slot del SO en los
      TRES espacios como ``{base}/{ESPACIO}`` (``crear_perfil_default``), con
      env forzado a esa base y unidad sobre ella.

    El orden del accept-list es BINDIENTE (R4): canonico → clave del perfil →
    ruta aparente → ``ValueError``. Un ``espacio`` que no es ni canonico ni
    clave del perfil ni ruta → ``ValueError``. Sin perfil nuevo → ``ValueError``
    claro (nunca onboarding silencioso como ``resolver_perfil``). Devuelve
    ``{"perfil", "env", "unidad"}`` y NO toca ``os.environ``: la propagacion
    la hace el widget (S4).
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    if espacio in _ESPACIOS or espacio in perfil:
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
            f"(esperado {', '.join(_ESPACIOS)}, un espacio extra del perfil "
            f"o una base de proyecto)"
        )
    actualizado = _copia_con_slot(perfil, so, slots)
    rutas_engine.guardar_perfiles(ruta_store, {usuario: actualizado})
    env = injector.armar_estado_env(actualizado, so, ruta_plato, base=base_env)
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(raiz_nueva),
    }


def guardar_base_unificada(usuario, ruta_store, so, base="", ruta_plato=""):
    """Persiste UNA base en los TRES espacios del ``so`` (modo simple, mockup).

    Es el corte de escritura del modo SIMPLE del widget: una sola base de
    proyecto rellena el slot ``(espacio, so)`` de cada espacio canonico con
    ``{base}/{ESPACIO}`` (``crear_perfil_default``, misma regla que el modo
    TODOS transitorio de ``preparar_cambio_base``). READ-MERGE-WRITE bajo el
    lock de ``guardar_perfiles``: otros SO, otras raices (otros espacios del
    mismo SO se reemplazan por diseno) y otros usuarios quedan intactos.

    Base vacia → ``ValueError`` (``_normalizar_ruta``); sin perfil nuevo →
    ``ValueError`` claro (nunca onboarding silencioso). El env sale de
    ``armar_estado_env`` con la base como PROJECT_ROOT (fallback del corte).
    Devuelve ``{"perfil", "env", "unidad"}`` y NO toca ``os.environ``: la
    propagacion la hace el widget.
    """
    raiz_nueva = _normalizar_ruta(base)
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    perfil_slot = rutas_engine.crear_perfil_default(base=raiz_nueva)
    slots = {esp: perfil_slot[esp][so] for esp in _ESPACIOS}
    actualizado = _copia_con_slot(perfil, so, slots)
    rutas_engine.guardar_perfiles(ruta_store, {usuario: actualizado})
    env = injector.armar_estado_env(actualizado, so, ruta_plato, base=raiz_nueva)
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(raiz_nueva),
    }


# --- Espacios extra: validacion + add/remove (spec panel-helper, R2/R8/D7) ----


def sanitizar_espacio_extra(nombre, perfil):
    """Valida y sanitiza el NOMBRE de un espacio extra (spec panel-helper).

    Delega la sanitizacion al motor (``rutas_engine._clave_env_para_espacio``,
    fuente unica de verdad): UPPER, ``A-Z0-9`` conservado, espacio→``_``,
    colapso y strip; el motor ya rechaza vacio tras sanitizar, ``/``/``{}``
    (R8) y ``HOSTS``/``DEFAULT`` (R2). Ademas se rechaza AQUI: un resultado
    que colisiona con un espacio CANONICO (``TO_VFX``/``COMP``/``FROM_VFX``,
    el trio fijo de ``PYTHON_*``), el literal ``PROJECT_ROOT`` (reservado) y
    un resultado que ya existe entre los extras del perfil (duplicado
    intra-extra). Devuelve la clave sanitizada, que ES la clave de store del
    espacio extra.
    """
    s = rutas_engine._clave_env_para_espacio(nombre)
    if s in _ESPACIOS:
        raise ValueError(
            f"El espacio extra {nombre!r} colisiona con el espacio canonico {s!r}"
        )
    if s == "PROJECT_ROOT":
        raise ValueError(f"El nombre {nombre!r} esta reservado (PROJECT_ROOT)")
    extras_existentes = (
        {clave for clave in perfil if clave not in _ESPACIOS}
        if isinstance(perfil, dict)
        else set()
    )
    if s in extras_existentes:
        raise ValueError(f"Ya existe un espacio extra llamado {s!r}")
    return s


def agregar_espacio_extra(usuario, ruta_store, so, nombre, nueva_ruta):
    """Persiste un espacio EXTRA nuevo y devuelve DATA (spec panel-helper, D7).

    Valida el nombre via ``sanitizar_espacio_extra`` (canonicos, legacy
    ``hosts``/``default``, ``PROJECT_ROOT``, duplicados intra-extra y nombres
    path-like/JSON-reservados → ``ValueError``) y mergea
    ``{usuario: {<clave>: {<so>: nueva_ruta}}}`` por ``guardar_perfiles``
    (READ-MERGE-WRITE bajo lock): todos los demas espacios, extras y usuarios
    quedan intactos. Sigue la convencion de slot de los demas cortes: el
    espacio nuevo nace con SOLO la raiz del ``so`` inyectado (los otros SO se
    completan luego desde el widget). Sin perfil nuevo → ``ValueError`` claro
    (nunca onboarding silencioso y, por R3, nunca un store extras-only).
    Devuelve ``{"perfil", "env", "unidad"}`` como datos y NO toca
    ``os.environ``: la propagacion la hace el widget (S4).
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    clave = sanitizar_espacio_extra(nombre, perfil)
    raiz_nueva = _normalizar_ruta(nueva_ruta)
    rutas_engine.guardar_perfiles(ruta_store, {usuario: {clave: {so: raiz_nueva}}})
    actualizado = rutas_engine.leer_perfiles(ruta_store)[usuario]
    env = injector.armar_estado_env(actualizado, so, "")
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(raiz_nueva),
    }


def eliminar_espacio_extra(usuario, ruta_store, espacio, so):
    """Elimina UN espacio extra del perfil y devuelve DATA (spec, D7).

    Delega al motor (``eliminar_espacio_store``: READ-POP-WRITE bajo lock);
    el motor rechaza espacios CANONICOS (D1, trio inmutable) y usuarios
    ausentes, y una clave ausente es no-op byte-identico. El helper valida
    ademas la forma del perfil antes de escribir (sin perfil nuevo →
    ``ValueError`` claro) y recomputa env + unidad sobre el perfil resultante
    para el ``so`` inyectado. La firma lleva ``so`` (D7, desviacion documentada
    de la firma minimal de la spec: el env y la unidad del contrato
    ``{"perfil", "env", "unidad"}`` se resuelven para el SO inyectado). NO
    toca ``os.environ``: la propagacion la hace el widget (S4).
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    perfil = perfiles.get(usuario)
    if rutas_engine.detectar_forma_perfil(perfil) != "nuevo":
        raise ValueError(
            f"No hay perfil activo para '{usuario}': complete el onboarding primero"
        )
    store = rutas_engine.eliminar_espacio_store(ruta_store, usuario, espacio)
    actualizado = store[usuario]
    env = injector.armar_estado_env(actualizado, so, "")
    base_actual = _raiz_para_so(actualizado, so)
    return {
        "perfil": actualizado,
        "env": env,
        "unidad": entorno.estado_unidad(base_actual),
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


# --- Seleccion activa por estacion (local, nunca en el store del proyecto) ----


def _ruta_seleccion(seleccion_path):
    """Ruta del archivo de seleccion: la inyectada o la default por estacion."""
    if seleccion_path:
        return os.path.abspath(str(seleccion_path))
    return os.path.expanduser(_RUTA_SELECCION_DEFAULT)


def _leer_datos_seleccion(ruta):
    """JSON de seleccion como dict; ausente/corrupto/no-dict → ``{}``."""
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def cargar_seleccion(ruta_store, seleccion_path=None):
    """Perfil activo guardado para ``ruta_store`` (por estacion, local).

    Lee ``~/.config/saman/seleccion.json`` con forma ``{"stores": {"<ruta_
    store>": "<nombre_perfil>"}}`` y devuelve el nombre o ``None`` (archivo
    ausente, corrupto, sin envelope o sin entrada para ese store). La ruta
    es parametrizable (``seleccion_path``) para tests. Puro: no muta el store
    de perfiles ni ``os.environ``.
    """
    ruta = _ruta_seleccion(seleccion_path)
    datos = _leer_datos_seleccion(ruta)
    stores = datos.get("stores")
    if not isinstance(stores, dict):
        return None
    nombre = stores.get(str(ruta_store))
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    return nombre


def guardar_seleccion(ruta_store, nombre, seleccion_path=None):
    """Persiste el perfil activo de ``ruta_store`` (merge atomico, local).

    Merge sobre ``~/.config/saman/seleccion.json``: los otros stores
    guardados se conservan y solo cambia la entrada de ``ruta_store``.
    Escritura atomica (tmp del mismo directorio + ``os.replace``), parent
    dirs creados lazy. Devuelve ``True`` si persiste; ``False`` si el nombre
    no es valido o la escritura falla. Nunca toca el store de perfiles.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        return False
    ruta = _ruta_seleccion(seleccion_path)
    datos = _leer_datos_seleccion(ruta)
    stores = datos.get("stores")
    if not isinstance(stores, dict):
        stores = {}
        datos["stores"] = stores
    stores[str(ruta_store)] = nombre.strip()
    contenido = json.dumps(datos, ensure_ascii=False, indent=2)
    try:
        directorio = os.path.dirname(os.path.abspath(ruta)) or "."
        os.makedirs(directorio, exist_ok=True)
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(
                prefix=os.path.basename(ruta) + ".", suffix=".tmp", dir=directorio
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(contenido)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, ruta)
            tmp = None  # ya reemplazado: nada que limpiar
        finally:
            if tmp is not None:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    except OSError:
        return False
    return True


# --- Renombrar perfil (re-key de las 9 raices, lock del motor) ---------------


def renombrar_perfil(ruta_store, nombre_viejo, nombre_nuevo):
    """Renombra un perfil conservando sus 9 raices; puro pero lock-guarded.

    Validacion de lectura clara sin escribir (nombre viejo inexistente,
    nombre nuevo ya tomado, nombre vacio o sin cambio → ``ValueError``) y
    delegacion del READ-RENAME-WRITE ATOMICO al motor
    (``renombrar_perfil_store``: re-lee y re-valida BAJO el lock, D3, y
    escribe con tmp + ``os.replace``). Devuelve el dict interno actualizado.
    """
    if not isinstance(nombre_nuevo, str) or not nombre_nuevo.strip():
        raise ValueError("El nombre del perfil no puede estar vacio")
    if nombre_viejo == nombre_nuevo:
        raise ValueError("El nombre del perfil no cambia")
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    if nombre_viejo not in perfiles:
        raise ValueError(f"No existe el perfil '{nombre_viejo}'")
    if nombre_nuevo in perfiles:
        raise ValueError(f"Ya existe un perfil llamado '{nombre_nuevo}'")
    return rutas_engine.renombrar_perfil_store(ruta_store, nombre_viejo, nombre_nuevo)


def onboarding_perfil(nombre, ruta_store, base, so, ruta_plato="", seleccion_path=None):
    """Onboarding con nombre libre + seleccion activa por estacion (wrapper).

    Encadena ``preparar_onboarding`` (asegurar_perfil con lock y slotting de
    la base) y ``guardar_seleccion`` (persiste la seleccion activa de este
    store en la estacion local). Devuelve el mismo contrato de datos
    ``{"perfil", "env", "unidad"}`` sin tocar ``os.environ``.
    """
    resultado = preparar_onboarding(nombre, ruta_store, base, so, ruta_plato)
    guardar_seleccion(ruta_store, nombre, seleccion_path)
    return resultado