"""
SamanTools.ui.path_manager — helper PURO del panel Path Manager (Ctrl+Alt+R),
cambio path-manager-panel, slice P1.

Divide el trabajo en capa pura / widget fino (precedente del injector):
este modulo es 100% puro — NO importa nuke ni PySide, NO lee ni muta
``os.environ`` y recibe identidad (``usuario``/``hostname``), SO y ruta del
store como parametros inyectados. Devuelve DATOS; el widget (P2) renderiza
y aplica el env via ``injector.cachear_env`` + ``aplicar_entorno``.

  - ``estado_panel``: corte de LECTURA — perfil activo (roots por plataforma),
    base del SO actual, estado de unidad y marcador de onboarding para
    desconocidos. Nunca escribe.
  - ``detectar_desconocido``: deteccion SOLO-LECTURA que replica la escalera
    de precedencia D2 sobre el API publico ``leer_perfiles`` (par exacto →
    user-only default → hostname ajeno → miss). NUNCA llama a
    ``resolver_perfil`` (que haria onboarding) y NUNCA escribe (D2).
  - ``_emparejar_con_fuente``: espejo del emparejador privado del motor que,
    ademas, reporta el tipo de match alcanzado (``exact``/``default``/
    ``foreign-host``) y el usuario dueno; el cambio de base D7 lo necesita.
  - ``preparar_cambio_base``: corte de ESCRITURA (REQ-4, D7) — READ-MERGE-
    WRITE bajo el lock de ``guardar_perfiles``: cambia SOLO la entrada matched
    (exact/foreign-host → ``hosts[hostname]``; user-default → ``default`` +
    ``hosts[hostname]``); otras raices del perfil y otros usuarios quedan
    intactos. Devuelve ``{"perfil", "env", "unidad"}`` como datos.
  - ``preparar_onboarding``: corte de ESCRITURA (REQ-5, D3) — persiste el par
    via ``asegurar_perfil`` (lock-safe, slotting de la base inyectada) y
    devuelve ``{"perfil", "env", "unidad"}`` como datos.

Determinismo: inputs identicos → salidas identicas (el unico dato vivo,
``entorno.estado_unidad``, respeta timeout + cache del motor). Ninguna ruta
real del estudio: solo raices ficticias (``/Volumes/estudio/2026``,
``L:/VFX/2026``, ``/mnt/estudio/2026``).
"""

from ..core import entorno
from ..core import rutas_engine
from . import injector

# Tipos de match de la escalera D2 (espejo del motor con rastreo de origen).
_FUENTE_EXACTA = "exact"
_FUENTE_DEFAULT = "default"
_FUENTE_HOST_AJENO = "foreign-host"


# --- Emparejamiento solo-lectura (D2) ----------------------------------------


def _emparejar_con_fuente(user, hostname, perfiles):
    """Replica la escalera D2 y reporta el tipo de match alcanzado.

    Orden canonico del motor (``rutas_engine._emparejar_perfil``): par exacto
    ``perfiles[user]["hosts"][hostname]`` → ``("exact", user)``; user-only
    ``perfiles[user]["default"]`` → ``("default", user)``; hostname-only:
    primer usuario en orden de documento con ``hosts[hostname]`` →
    ``("foreign-host", dueno)``; miss → ``(None, None, None)`` (marcador de
    onboarding). NUNCA escribe ni resuelve: lectura pura para deteccion y
    para decidir el shape de escritura D7.
    """
    usuario = perfiles.get(user)
    if isinstance(usuario, dict):
        hosts = usuario.get("hosts")
        if isinstance(hosts, dict):
            roots = hosts.get(hostname)
            if isinstance(roots, dict):
                return roots, _FUENTE_EXACTA, user
        default = usuario.get("default")
        if isinstance(default, dict):
            return default, _FUENTE_DEFAULT, user
    for dueno, perfil in perfiles.items():
        if not isinstance(perfil, dict):
            continue
        hosts = perfil.get("hosts")
        if not isinstance(hosts, dict):
            continue
        roots = hosts.get(hostname)
        if isinstance(roots, dict):
            return roots, _FUENTE_HOST_AJENO, dueno
    return None, None, None


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


def estado_panel(ruta_store, usuario, hostname, so):
    """Estado de lectura del panel (REQ-1/REQ-2/REQ-3). Puro; sin escrituras.

    Devuelve ``{"conocido", "perfil", "base_actual", "unidad"}``:

    * ``conocido`` — ``True`` si el par resuelve a perfil (escalera D2, sin
      escribir); ``False`` si es desconocido (marcador de onboarding).
    * ``perfil`` — dict de roots por plataforma del match, o ``None``.
    * ``base_actual`` — root del perfil para el ``so`` inyectado, o ``None``.
    * ``unidad`` — ``entorno.estado_unidad(base_actual)`` (perfil conocido) o
      de la primera candidata de ``entorno.rutas_base(so)`` (sin perfil);
      timeout + cache respetados, nunca se cuelga en un mount muerto.
    """
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    roots, _fuente, _dueno = _emparejar_con_fuente(usuario, hostname, perfiles)
    if roots is None:
        return {
            "conocido": False,
            "perfil": None,
            "base_actual": None,
            "unidad": entorno.estado_unidad(_primera_candidata(so)),
        }
    base_actual = rutas_engine.ruta_para_plataforma(roots, so)
    return {
        "conocido": True,
        "perfil": roots,
        "base_actual": base_actual,
        "unidad": entorno.estado_unidad(base_actual),
    }


def detectar_desconocido(ruta_store, usuario, hostname):
    """``True`` si el par no resuelve a perfil alguno; ``False`` si resuelve.

    Lectura pura (D2): replica la escalera sobre ``leer_perfiles``, NUNCA
    escribe y NUNCA llama a ``resolver_perfil`` (que haria onboarding
    automatico). Store ausente o corrupto → ``True`` (no confirmable). Sin
    raise: la deteccion alimenta la UI, nunca debe romperla.
    """
    try:
        perfiles = rutas_engine.leer_perfiles(ruta_store)
    except ValueError:
        return True
    roots, _fuente, _dueno = _emparejar_con_fuente(usuario, hostname, perfiles)
    return roots is None


# --- Corte de escritura: cambio de base (REQ-4, D7) ---------------------------


def preparar_cambio_base(usuario, hostname, ruta_store, so, nueva_base, ruta_plato=""):
    """Persiste la nueva base del perfil matched y devuelve DATA (REQ-4, D7).

    READ-MERGE-WRITE bajo el lock de ``guardar_perfiles``: cambia SOLO la
    entrada matched — exact/foreign-host → ``hosts[hostname]`` del dueno;
    user-default → ``default`` + ``hosts[hostname]`` — y conserva las otras
    raices del perfil y los demas usuarios. Devuelve ``{"perfil", "env",
    "unidad"}``: el perfil actualizado, el env delta de
    ``injector.armar_estado_env`` (con la base nueva forzada) y el estado de
    unidad de la base nueva. NO toca ``os.environ``: la propagacion la hace
    el widget (P2). Sin match → ``ValueError`` claro (nunca onboarding
    silencioso como ``resolver_perfil``).
    """
    base_norm = _normalizar_base(nueva_base)
    perfiles = rutas_engine.leer_perfiles(ruta_store)
    roots, fuente, dueno = _emparejar_con_fuente(usuario, hostname, perfiles)
    if roots is None or fuente is None:
        raise ValueError(
            f"No hay perfil activo para '{usuario}' en '{hostname}': "
            "complete el onboarding primero"
        )
    nuevas_roots = dict(roots)
    nuevas_roots[so] = base_norm
    if fuente == _FUENTE_DEFAULT:
        rutas_engine.guardar_perfiles(
            ruta_store,
            {usuario: {"hosts": {hostname: nuevas_roots}, "default": nuevas_roots}},
        )
    else:
        rutas_engine.guardar_perfiles(
            ruta_store, {dueno: {"hosts": {hostname: nuevas_roots}}}
        )
    env = injector.armar_estado_env(nuevas_roots, so, ruta_plato, base=base_norm)
    return {
        "perfil": nuevas_roots,
        "env": env,
        "unidad": entorno.estado_unidad(base_norm),
    }


# --- Corte de escritura: onboarding (REQ-5, D3) -------------------------------


def preparar_onboarding(usuario, hostname, ruta_store, base, so, ruta_plato=""):
    """Persiste el onboarding del par y devuelve DATA (REQ-5, D3).

    Via ``asegurar_perfil`` (lock-safe): construye las 3 roots ficticias por
    plataforma con slotting de la base inyectada
    (``crear_perfil_default``: ``/Volumes/`` → macOS, ``^[A-Za-z]:`` →
    Windows, ``/mnt/`` → Linux); si otro proceso gano la carrera devuelve el
    perfil del ganador sin reescribir. Devuelve ``{"perfil", "env",
    "unidad"}``: las roots persistidas, el env delta de
    ``injector.armar_estado_env`` (con la raiz del SO actual como base) y el
    estado de unidad de esa raiz. NO toca ``os.environ``.
    """
    roots = rutas_engine.asegurar_perfil(usuario, hostname, ruta_store, base=base)
    base_so = roots.get(so)
    env = injector.armar_estado_env(roots, so, ruta_plato, base=base_so)
    return {
        "perfil": roots,
        "env": env,
        "unidad": entorno.estado_unidad(base_so),
    }