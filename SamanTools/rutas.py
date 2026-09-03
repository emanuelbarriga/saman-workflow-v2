"""
SamanTools V2 compat shim — comps V1 (from SamanTools import rutas) kept alive; delegates to core.

Shim de compatibilidad del cambio load-contract (slice H2): mantiene vivo el
contrato de los comps V1 — que hacen ``from SamanTools import rutas;
rutas.actualizar(nuke.thisNode())`` — delegando TODA la logica al core puro y
al injector.

  - Constantes re-exportadas IDENTICAS a V1 (``SUFIJOS``, ``KNOBS_RUTAS_BASE``,
    ``KNOBS_VERSION_ACTUAL``, ``_KNOBS_A_MIGRAR``): sus valores se serializan
    en archivos ``.nk`` y NO pueden cambiar.
  - Facades FINAS con firmas V1 que delegan en ``SamanTools.core.entorno`` y
    ``SamanTools.core.nombres``; toda escritura de entorno pasa por
    ``SamanTools.ui.injector.aplicar_entorno`` respetando la cadena de
    precedencia (ADR-3): el env del render farm pre-existente gana, el env que
    el injector ya cacheo esta sesion gana (``_env_inyectado``), el override
    manual de root gana, y solo si nada de eso aplica manda el env derivado de
    los knobs del nodo. Idempotente e independiente del orden.
  - ``nuke`` se importa SOLO de forma diferida dentro de los cuerpos de
    funciones (try/except); los type hints de tipos Nuke son STRINGS
    (``"nuke.Node"``) para que el modulo importe headless en maquinas sin Nuke.
  - Stubs compat-only: ``crear_o_reutilizar``, ``cambiar_proyecto``,
    ``avisar_duplicados``, ``refrescar_fuentes_boton`` y ``ruta_nk_por_defecto``
    son no-ops de import seguro (devuelven ``None``), marcados como nunca
    revividos en V2 en su docstring.

SamanTools/core NO se toca: el shim solo lo importa. Ninguna ruta real del
estudio: solo raices ficticias (``/Volumes/estudio/2026``, ``L:/VFX/2026``,
``/mnt/estudio/2026``).
"""

import os
import re

from .core import entorno
from .core import nombres
from .ui import injector

SUFIJOS = {"MacServer": "MAC", "Windows": "WINDOWS", "Artist": "ARTIST"}

# Guarda antireentrada de refrescar_estado: evita un loop infinito si un
# setValue dentro de knobChanged vuelve a disparar knobChanged.
_refrescando = False


# ---------------------------------------------------------------------------
# Helpers puros compartidos (copias finas: el core no tiene equivalente)
# ---------------------------------------------------------------------------


def _texto_estado(estado):
    """Texto legible para el knob EstadoUnidad a partir del dict de estado."""
    base = "Conectado" if estado.get("conectado") else "Desconectado"
    detalle = estado.get("detalle") or ""
    return (base + " - " + detalle) if detalle else base


def _reescribir_proyecto_en_rutas(rutas_dict, proy):
    """
    Puro: reemplaza el segmento de proyecto en un dict de rutas base.

    La regex es la misma que vivia embebida en el gizmo: toma el segmento
    inmediatamente anterior a TO_VFX|COMP|FROM_VFX y lo sustituye por `proy`.
    Devuelve (nuevo_dict, cambios). Copia fina de V1: el core no tiene
    equivalente (candidata a promover a core.nombres en un cambio futuro).
    """
    nuevo = dict(rutas_dict or {})
    cambios = 0
    for k_name, val in nuevo.items():
        if not val:
            continue
        nueva_ruta = re.sub(
            r"/[^/]+/(TO_VFX|COMP|FROM_VFX)(/|$)",
            "/" + proy + r"/\1\2",
            str(val),
            flags=re.IGNORECASE,
        )
        if nueva_ruta != val:
            nuevo[k_name] = nueva_ruta
            cambios += 1
    return nuevo, cambios


# ---------------------------------------------------------------------------
# Acceso lazy a nuke (nunca a nivel de modulo)
# ---------------------------------------------------------------------------


def _this_node():
    """nuke.thisNode() lazy y tolerante; None fuera de Nuke o si falla."""
    try:
        import nuke

        return nuke.thisNode()
    except Exception:
        return None


def _nuke_root():
    """nuke.root() lazy y tolerante; None fuera de Nuke o si falla."""
    try:
        import nuke

        return nuke.root()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sincronizacion de knobs del nodo (nuke-bound, tolerante a knobs ausentes)
# ---------------------------------------------------------------------------


def _sufijo_activo(n):
    """Sufijo del usuario activo del nodo; None si invalido o ausente."""
    try:
        if "UsuarioActivo" not in n.knobs():
            return None
        return SUFIJOS.get(str(n["UsuarioActivo"].value()).strip())
    except Exception:
        return None


def _recomendar_usuario(n):
    """
    Refuerza la recomendacion de usuario en nodos con seccion de entorno
    (knob UsuarioRecomendado presente): actualiza el texto informativo segun
    SO y rellena UsuarioActivo SOLO si esta vacio o NO es un valor valido;
    NUNCA pisa un valor valido elegido a mano por el artista.
    """
    try:
        if "UsuarioRecomendado" not in n.knobs():
            return
        so = entorno.detectar_so()
        recomendado = entorno.usuario_activo(so)
        n["UsuarioRecomendado"].setValue("Usuario recomendado segun SO: " + recomendado)
        if "UsuarioActivo" in n.knobs():
            actual = str(n["UsuarioActivo"].value()).strip()
            if actual not in SUFIJOS:
                n["UsuarioActivo"].setValue(recomendado)
    except Exception:
        pass


def _sincronizar_entorno(n):
    """
    Sincroniza SO_Detectado/EstadoUnidad con core.entorno (SO detectado y
    estado de la unidad desde la primera ruta base disponible). Tolerante a
    knobs ausentes (nodos viejos o escenarios de test con solo UsuarioActivo +
    rutas).
    """
    try:
        so = entorno.detectar_so()
    except Exception:
        return
    try:
        if "SO_Detectado" in n.knobs():
            n["SO_Detectado"].setValue(so)
    except Exception:
        pass
    try:
        if "EstadoUnidad" in n.knobs():
            ruta_base = entorno.primera_ruta_disponible(so)
            estado = entorno.estado_unidad(ruta_base)
            n["EstadoUnidad"].setValue(_texto_estado(estado))
    except Exception:
        pass


def _sincronizar_plano(n):
    """
    Detecta proyecto/capitulo/plano desde nuke.root().name() via
    core.nombres.parsear_plato y los muestra en los knobs informativos
    ProyectoDetectado/CapituloDetectado/PlanoDetectado. Tolerante: knobs
    ausentes, sin root o sin parseo no rompen.
    """
    try:
        import nuke

        ruta = nuke.root().name()
    except Exception:
        ruta = ""
    datos = None
    if ruta:
        try:
            datos = nombres.parsear_plato(ruta)
        except Exception:
            datos = None
    valores = {
        "ProyectoDetectado": (datos or {}).get("proyecto") or "",
        "CapituloDetectado": (datos or {}).get("capitulo") or "",
        "PlanoDetectado": (datos or {}).get("plano") or "",
    }
    if not any(str(v) for v in valores.values()):
        return
    try:
        for nombre, valor in valores.items():
            if nombre in n.knobs():
                n[nombre].setValue(str(valor))
    except Exception:
        pass


def _aplicar_visibilidad(n, sufijo):
    """
    Muestra solo los knobs y separadores del grupo del usuario activo.

    Tolerancia TOTAL: si un knob no existe o no expone setVisible (nodos
    viejos, stub de tests), se saltea sin lanzar excepciones.
    """
    grupos = {
        "MAC": [
            "TO_VFX_SERVER_MAC",
            "comp_SERVER_MAC",
            "FROM_VFX_SERVER_MAC",
            "RutaMacServer",
        ],
        "WINDOWS": [
            "TO_VFX_SERVER_WINDOWS",
            "comp_SERVER_WINDOWS",
            "FROM_VFX_SERVER_WINDOWS",
            "RutaWindows",
        ],
        "ARTIST": [
            "TO_VFX_SERVER_ARTIST",
            "comp_SERVER_ARTIST",
            "FROM_VFX_SERVER_ARTIST",
            "RutaArtist",
        ],
    }
    for suf, knobs in grupos.items():
        visible = suf == sufijo
        for nombre in knobs:
            try:
                if nombre not in n.knobs():
                    continue
                setter = getattr(n[nombre], "setVisible", None)
                if setter is not None:
                    setter(visible)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Env derivado de knobs + aplicacion con la precedencia del injector (ADR-3)
# ---------------------------------------------------------------------------


def _env_desde_knobs(n, sufijo):
    """
    Env TCL derivado SOLO de los knobs del nodo Rutas (ADR-3, knob-driven).

    PROYECT_ROOT se deduce de la ruta TO_VFX (``{base}/{proyecto}/TO_VFX/``):
    quita los dos ultimos segmentos, quedando la base del anio. Contrato V2:
    PROJECT_ROOT + PYTHON_TO_VFX/COMP/FROM_VFX.
    """
    env = {}
    to_vfx = ""
    for nombre, clave_env in (
        ("TO_VFX_SERVER_" + sufijo, "PYTHON_TO_VFX"),
        ("comp_SERVER_" + sufijo, "PYTHON_COMP"),
        ("FROM_VFX_SERVER_" + sufijo, "PYTHON_FROM_VFX"),
    ):
        try:
            valor = str(n[nombre].value())
        except Exception:
            valor = ""
        env[clave_env] = valor
        if nombre.startswith("TO_VFX_SERVER_"):
            to_vfx = valor
    base = to_vfx.strip().rstrip("/")
    if base:
        env["PROJECT_ROOT"] = base.rsplit("/", 2)[0]
    return env


def _aplicar_env_shim(env):
    """
    Aplica env por el injector respetando la cadena de precedencia (ADR-3).

    Si el injector ya escribio env esta sesion (``_env_inyectado``) NO se
    escribe: el env del perfil gana. Si no, pasa por el guard de precedencia
    del injector (farm env pre-existente gana; override de root gana) y solo
    se aplica lo que el guard devuelva, siempre via ``aplicar_entorno``.
    """
    if injector._env_inyectado:
        return
    root_override = injector._override_proyecto_desde_root(_nuke_root())
    final = injector._aplicar_precedencia(env, root_override, dict(os.environ))
    if final:
        injector.aplicar_entorno(final)


# ---------------------------------------------------------------------------
# Reads dinamicos [python ...] (copias de V1, nuke-bound)
# ---------------------------------------------------------------------------


def _capturar_reads_dinamicos():
    """Reads con ruta dinamica [python ...]: [(node, script, valor_actual)]."""
    try:
        import nuke

        todos = nuke.allNodes("Read")
    except Exception:
        return []
    reads = []
    for node in todos:
        try:
            if "file" not in node.knobs():
                continue
            script = node["file"].toScript()
            if "[python" in script.lower():
                reads.append((node, script, node["file"].value()))
        except Exception:
            continue
    return reads


def _re_evaluar_y_recargar(reads, forzar=False):
    """Re-evalua cada Read con su script y recarga si forzar o si el valor cambio.
    Devuelve cuantos reload ejecuto."""
    recargados = 0
    for node, script, anterior in reads:
        try:
            node["file"].fromScript(script)
            if forzar or node["file"].value() != anterior:
                node["reload"].execute()
                recargados += 1
        except Exception:
            continue
    return recargados


# ---------------------------------------------------------------------------
# Adaptador legacy: del nodo a env, con efectos de knob
# ---------------------------------------------------------------------------


def _sincronizar_knobs(n, sufijo):
    """Sincroniza los knobs informativos del nodo (usuario, entorno, plano,
    visibilidad) sin tocar variables de entorno."""
    _recomendar_usuario(n)
    _sincronizar_entorno(n)
    _sincronizar_plano(n)
    _aplicar_visibilidad(n, sufijo)


def _set_ruta_actual(n, env):
    """Etiqueta RutaActual (mismo formato V1); solo si el nodo viejo la tiene."""
    try:
        if "RutaActual" not in n.knobs():
            return
        texto_ruta = (
            "TO_VFX: {0} [PYTHON_TO_VFX]\n"
            "COMP: {1} [PYTHON_COMP]\n"
            "FROM_VFX: {2} [PYTHON_FROM_VFX]"
        ).format(
            env.get("PYTHON_TO_VFX", ""),
            env.get("PYTHON_COMP", ""),
            env.get("PYTHON_FROM_VFX", ""),
        )
        n["RutaActual"].setValue(texto_ruta)
    except Exception:
        pass


def _aplicar_proyecto_inner(n):
    """
    ADAPTADOR legacy: arma el env desde los knobs del nodo y lo aplica con la
    precedencia del injector (ADR-3). Conserva los efectos de knob del nodo
    (entorno, plano, visibilidad, RutaActual). Devuelve True si aplico, o None
    (CENTINELA) si el usuario activo no es valido (no aplico nada).
    """
    sufijo = _sufijo_activo(n)
    if not sufijo:
        return None

    _sincronizar_knobs(n, sufijo)
    env = _env_desde_knobs(n, sufijo)
    _aplicar_env_shim(env)
    _set_ruta_actual(n, env)
    return True


# ---------------------------------------------------------------------------
# Facades publicas (firmas V1; delegacion a core + injector)
# ---------------------------------------------------------------------------


def actualizar(n: "nuke.Node" = None) -> bool:
    """
    Actualiza TO_VFX/COMP/FROM_VFX del proyecto activo y refresca los Reads.

    Conserva el orden critico de la version historica: captura los Reads
    dinamicos ([python ...]) ANTES de escribir las variables PYTHON_* (asi
    re-evalua con la ruta ANTIGUA y sabe si resolvio distinto), y solo recarga
    los Reads cuya ruta resuelta realmente cambio. El env se escribe via el
    injector respetando ADR-3 (nunca pisa el env que el injector ya escribio
    esta sesion). Se llama desde el knobChanged del nodo.
    """
    if n is None:
        n = _this_node()
    if n is None:
        return False

    reads = _capturar_reads_dinamicos()
    resultado = _aplicar_proyecto_inner(n)
    if resultado is None:
        return False
    _re_evaluar_y_recargar(reads, forzar=False)
    return bool(resultado)


def aplicar_proyecto(n: "nuke.Node" = None) -> bool:
    """Boton/programa: aplica el proyecto activo (variables PYTHON_* + entorno +
    visibilidad) SIN recargar Reads. Devuelve True si aplico, False si no (o
    si el usuario activo no es valido)."""
    if n is None:
        n = _this_node()
    if n is None:
        return False
    return bool(_aplicar_proyecto_inner(n))


def refrescar_fuentes(n: "nuke.Node" = None, forzar: bool = False) -> int:
    """Re-evalua los Reads dinamicos [python ...] y recarga.

    - forzar=False: recarga SOLO los que cambiaron su ruta resuelta.
    - forzar=True: recarga TODOS (boton "Refrescar Fuentes").
    Devuelve la cantidad recargada."""
    if n is None:
        n = _this_node()
    if n is None:
        return 0
    reads = _capturar_reads_dinamicos()
    return _re_evaluar_y_recargar(reads, forzar=forzar)


# ---------------------------------------------------------------------------
# Botones del nodo Rutas: Cambiar Proyecto y Refrescar Fuentes
# ---------------------------------------------------------------------------

KNOBS_RUTAS_BASE = (
    "TO_VFX_SERVER_MAC", "comp_SERVER_MAC", "FROM_VFX_SERVER_MAC",
    "TO_VFX_SERVER_WINDOWS", "comp_SERVER_WINDOWS", "FROM_VFX_SERVER_WINDOWS",
    "TO_VFX_SERVER_ARTIST", "comp_SERVER_ARTIST", "FROM_VFX_SERVER_ARTIST",
)


def refrescar_estado(n: "nuke.Node" = None) -> bool:
    """
    Refresca los knobs de estado del nodo Rutas: recomendacion de usuario,
    visibilidad del grupo activo, SO_Detectado, EstadoUnidad (via
    core.entorno) y tile_color (verde 0x6aff55ff conectado / rojo 0xff3b30ff
    desconectado). Solo toca knobs que existan; nunca lanza. Devuelve True si
    pudo evaluar el estado, False si no (o si hay reentrada).
    """
    global _refrescando
    if _refrescando:
        return False
    if n is None:
        n = _this_node()
    if n is None:
        return False

    _refrescando = True
    try:
        so = entorno.detectar_so()
        _recomendar_usuario(n)

        sufijo = _sufijo_activo(n)
        if sufijo:
            _aplicar_visibilidad(n, sufijo)

        ruta_base = entorno.primera_ruta_disponible(so)
        estado = entorno.estado_unidad(ruta_base)
        color = 0x6aff55ff if estado["conectado"] else 0xff3b30ff

        try:
            if "SO_Detectado" in n.knobs():
                n["SO_Detectado"].setValue(so)
        except Exception:
            pass
        try:
            if "EstadoUnidad" in n.knobs():
                n["EstadoUnidad"].setValue(_texto_estado(estado))
        except Exception:
            pass
        _sincronizar_plano(n)
        try:
            if "tile_color" in n.knobs():
                n["tile_color"].setValue(color)
        except Exception:
            pass
        return True
    finally:
        _refrescando = False


# ---------------------------------------------------------------------------
# Gestion del nodo unico Rutas (maximo UNO por proyecto)
# ---------------------------------------------------------------------------

KNOBS_VERSION_ACTUAL = frozenset(
    {
        "SeccionEntorno",
        "SO_Detectado",
        "EstadoUnidad",
        "UsuarioRecomendado",
        "ProyectoDetectado",
        "CapituloDetectado",
        "PlanoDetectado",
    }
)

_KNOBS_A_MIGRAR = (
    "string",
    "UsuarioActivo",
    "TO_VFX_SERVER_MAC",
    "comp_SERVER_MAC",
    "FROM_VFX_SERVER_MAC",
    "TO_VFX_SERVER_WINDOWS",
    "comp_SERVER_WINDOWS",
    "FROM_VFX_SERVER_WINDOWS",
    "TO_VFX_SERVER_ARTIST",
    "comp_SERVER_ARTIST",
    "FROM_VFX_SERVER_ARTIST",
)


def es_nodo_rutas(n) -> bool:
    """
    True si el nodo es uno de Rutas, identificado por sus knobs de control:
    UsuarioActivo + alguno de los knobs TO_VFX_SERVER_*. No depende del
    nombre: el artista puede renombrarlo y aun asi se detecta. Tolerante a
    None y a nodos raros.
    """
    if n is None:
        return False
    try:
        knobs = n.knobs()
    except Exception:
        return False
    if "UsuarioActivo" not in knobs:
        return False
    return any(
        s in knobs
        for s in ("TO_VFX_SERVER_MAC", "TO_VFX_SERVER_WINDOWS", "TO_VFX_SERVER_ARTIST")
    )


def encontrar_nodos_rutas() -> list:
    """Lista de todos los nodos Rutas presentes en el script actual."""
    try:
        import nuke

        todos = nuke.allNodes()
    except Exception:
        return []
    return [n for n in todos if es_nodo_rutas(n)]


def es_version_actual(n) -> bool:
    """
    True si el nodo tiene TODOS los knobs de la version actual del nodo
    (seccion de entorno informativo). Un nodo viejo no los tiene.
    """
    if n is None:
        return False
    try:
        knobs = n.knobs()
    except Exception:
        return False
    return KNOBS_VERSION_ACTUAL.issubset(knobs)


# ---------------------------------------------------------------------------
# Stubs compat-only (nunca revividos en V2)
# ---------------------------------------------------------------------------


def crear_o_reutilizar(ruta_nk=None):
    """COMPAT-ONLY: no-op en V2 (nunca revivido); V1 creaba el nodo unico Rutas."""
    return None


def cambiar_proyecto(n=None):
    """COMPAT-ONLY: no-op en V2 (nunca revivido); V1 reescribia las 9 rutas base."""
    return None


def avisar_duplicados(n=None):
    """COMPAT-ONLY: no-op en V2 (nunca revivido); V1 avisaba nodos Rutas duplicados."""
    return None


def refrescar_fuentes_boton(n=None):
    """COMPAT-ONLY: no-op en V2 (nunca revivido); V1 recargaba TODOS los Reads."""
    return None


def ruta_nk_por_defecto():
    """COMPAT-ONLY: no-op en V2 (nunca revivido); V1 devolvia la ruta del .nk."""
    return None