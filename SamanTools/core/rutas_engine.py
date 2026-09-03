"""
SamanTools.core.rutas_engine - Motor de rutas de composicion V2 (perfil-por-usuario, S1).

El motor opera con el esquema D1/AD1: un store ``nuke_profiles.json`` con
envelope ``{"perfiles": {usuario: {TO_VFX|COMP|FROM_VFX: {macOS|Windows|Linux:
root}}}}`` — SIN hostname ni escalera (AD2; la resolucion es SOLO por usuario).
Los tres espacios son INDEPENDIENTES (pueden vivir en discos distintos) y cada
uno tiene su root por plataforma.

  - ``leer_perfiles`` / ``guardar_perfiles``: lectura con envelope; escritura
    ATOMICA (temporal en el mismo directorio + ``os.replace``) y, bajo lock,
    READ-MERGE-WRITE POR ESPACIO: nunca se reemplaza a ciegas otro espacio ni
    otro usuario; una entrada legacy (``hosts``/``default`` sin espacios) se
    REEMPLAZA por la forma nueva en la escritura (AD1). ``.saman/`` se crea
    lazy bajo lock (``os.makedirs(dirname, exist_ok=True)``), nunca en lectura.
  - ``detectar_forma_perfil``: purga — ``"nuevo"`` si hay al menos un espacio
    valido; ``"legacy"`` en caso contrario (hosts/default o sin datos). Es el
    flag solo-lectura que la UI usara para advertir la regeneracion.
  - ``crear_perfil_default``: perfil 3x3 con raices ficticias
    (``/Volumes/estudio/2026/CINE/{ESPACIO}``, ``L:/VFX/2026/CINE/{ESPACIO}``,
    ``/mnt/estudio/2026/CINE/{ESPACIO}``) y slotting de la base inyectada por
    forma (``/Volumes/`` → macOS, ``^[A-Za-z]:`` → Windows, ``/mnt/`` → Linux):
    el SO del slot rellena los tres espacios con ``{base}/{ESPACIO}``.
  - ``ruta_para_espacio``: root del espacio para la plataforma o ``None``.
  - ``resolver_perfil(user, path)``: ``perfiles.get(user)`` directo (sin
    escalera); desconocido o legacy → onboarding via ``asegurar_perfil``.
    NUNCA lanza por desconocido ni devuelve ``None``.
  - ``asegurar_perfil(user, path, base=None)``: onboarding bajo el lock con
    re-read y re-deteccion (carrera ganada → perfil del ganador sin
    reescribir); si no, merge por usuario de la forma 3x3 y escritura atomica.
  - ``relativizar``/``absolutizar`` (D5 two-track): relativizacion string-level
    ``[getenv PROJECT_ROOT]`` — la comparacion de prefijo se hace sobre una
    copia canonica case-folded (backslashes a slashes, strip, ``rstrip("/")``,
    ``.lower()`` total) y la emision trocea el ORIGINAL normalizado a slashes
    con casing intacto. ``absolutizar`` sustituye la base inyectada VERBATIM.
  - ``get_context(perfil, ruta_plato)``: ``{proyecto, plano, version,
    carpeta_salida, espacio, so, project_root}`` derivado SOLO de
    perfil+plato inyectados; ``project_root`` por CORTE ESTRUCTURAL
    (``raiz_proyecto_desde_ruta``); ``espacio``/``so`` de la root del espacio
    que prefija el plato (``_espacio_prefijado``); ``proyecto`` = segmento de
    proyecto de ese corte con fallback al token del nombre;
    ``carpeta_salida`` SIEMPRE ``"[getenv PROJECT_ROOT]/COMP/"`` (AD3).
  - ``variables_entorno(contexto, perfil=None)``: contrato TCL como DATOS —
    ``PROJECT_ROOT`` por corte (NUNCA base); PYTHON_TO_VFX/COMP/FROM_VFX desde
    las raices del perfil para el SO actual; espacio faltante → fallback
    hermano ``reconstruir_rutas(dirname, basename)`` del corte (AD7, sin slash
    final); clave irresoluble OMITIDA, nunca ``""``. NUNCA muta
    ``os.environ``: la inyeccion la hace la capa de carga, no el motor.

Lock (D6): exclusivo sobre un archivo HERMANO ``path + ".lock"`` — nunca el
target: ``os.replace`` cambia el inode y un lock ahi quedaria huerfano tras la
primera escritura. fcntl (POSIX) / msvcrt (Windows) / no-op documentado;
3 intentos de <=2.0 s y ``TimeoutError`` al agotar (nunca overwrite silencioso);
``_lock_clase`` es factory con plataforma inyectada para testear ambas ramas.

Modulo autocontenido y 100% stdlib, sin ambiente (getpass/socket/platform en
la logica: todo parametro es inyectado). Ninguna ruta real del estudio: solo
raices ficticias.
"""

import contextlib
import json
import os
import re
import tempfile
import time

from .entorno import raiz_proyecto_desde_ruta, reconstruir_rutas, sufijo_so
from .nombres import parsear_plato

# Espacios del esquema 3x3 (AD1) y razas de SO soportadas.
_ESPACIOS = ("TO_VFX", "COMP", "FROM_VFX")
_PLATAFORMAS_SOPORTADAS = ("macOS", "Windows", "Linux")

# Raices ficticias por plataforma (nunca rutas reales del estudio).
_RAICES_FICTICIAS = {
    "macOS": "/Volumes/estudio/2026",
    "Windows": "L:/VFX/2026",
    "Linux": "/mnt/estudio/2026",
}
_PROYECTO_FICTICIO = "CINE"

_INTENTOS_LOCK = 3
_PLAZO_INTENTO_S = 2.0
_PERIODO_POLL_S = 0.25

MENSAJE_LOCK_AGOTADO = "No se pudo adquirir lock de perfiles"


# --- Store: lectura / envelope -------------------------------------------------


def _leer_envelope(path):
    """Lee el envelope JSON completo del store; ``{}`` si falta el archivo.

    JSON invalido o raiz que no es un objeto → ``ValueError``: un store
    corrupto debe fallar en voz alta, nunca devolverse como vacio.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON de perfiles malformado en {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"El contenido de {path} debe ser un objeto JSON")
    return data


def leer_perfiles(path):
    """Carga el dict interno ``perfiles`` del store; ``{}`` si no existe (spec).

    Un archivo inexistente devuelve un store vacio sin lanzar; JSON malformado
    lanza ``ValueError``. El envelope envuelve los perfiles en ``{"perfiles":
    ...}`` (D1) y este devuelve SOLO el dict interno. Nunca crea ``.saman/``
    (AD6: solo escrituras lockean y crean el directorio).
    """
    envelope = _leer_envelope(path)
    inner = envelope.get("perfiles")
    if inner is None:
        return {}
    if not isinstance(inner, dict):
        raise ValueError(f"El envelope de {path} debe tener 'perfiles' como objeto JSON")
    return inner


# --- Escritura atomica ----------------------------------------------------------


def _escribir_atomico(path, contenido):
    """Escribe `contenido` de forma ATOMICA: tmp del mismo directorio + replace.

    El temporal vive en el MISMO directorio (mismo filesystem ⇒ os.replace
    atomico). Si algo falla, el temporal se limpia y el archivo original queda
    intacto.
    """
    directorio = os.path.dirname(os.path.abspath(path)) or "."
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directorio
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None  # ya fue reemplazado: nada que limpiar
    finally:
        if tmp is not None:
            try:
                os.remove(tmp)
            except OSError:
                pass


# --- Forma del perfil (AD1) -----------------------------------------------------


def detectar_forma_perfil(perfil):
    """Clasifica el perfil: ``"nuevo"`` (esquema 3x3) o ``"legacy"`` (AD1).

    ``"nuevo"`` si el dict tiene al menos un espacio valido (TO_VFX/COMP/
    FROM_VFX con valor dict). Cualquier otra cosa — un entry con
    ``hosts``/``default`` y sin espacios, un dict vacio, no-dict o ``None`` —
    es ``"legacy"``: la resolucion la tratara como desconocida y la escritura
    la regenerara con la forma nueva (flag solo-lectura para la UI).
    """
    if isinstance(perfil, dict):
        for espacio in _ESPACIOS:
            if isinstance(perfil.get(espacio), dict):
                return "nuevo"
    return "legacy"


# --- Merge por usuario (kernel compartido, D1/D3) --------------------------------


def _mezclar_perfil_usuario(store, user, perfil):
    """Merge de UN usuario en `store`: por ESPACIO, legacy reemplazado.

    Otros usuarios quedan intactos; dentro del usuario, los espacios ya
    conocidos conservan sus raices y solo se agregan/actualizan las entrantes
    (ADE1: espacios independientes). Si la entrada existente tiene forma
    LEGACY (hosts/default, D1) se REEMPLAZA entera por la forma entrante.
    Devuelve `store` (muta in-place: es el kernel de read-merge-write bajo
    lock).
    """
    if not isinstance(perfil, dict):
        raise ValueError(f"Perfil de '{user}' debe ser un objeto JSON")
    existing = store.get(user)
    if not isinstance(existing, dict):
        existing = {}
        store[user] = existing
    if detectar_forma_perfil(existing) == "legacy":
        # Reemplazo total de la forma vieja por la nueva (AD1: silent regen).
        store[user] = perfil
        return store
    for espacio, raices in perfil.items():
        if not isinstance(raices, dict):
            raise ValueError(f"El espacio '{espacio}' de '{user}' debe ser un objeto JSON")
        dest = existing.get(espacio)
        if not isinstance(dest, dict):
            dest = {}
            existing[espacio] = dest
        for so, root in raices.items():
            dest[so] = root
    return store


def guardar_perfiles(path, perfiles):
    """Persiste el store interno bajo lock y de forma atomica (spec).

    Bajo el lock exclusivo hace READ-MERGE-WRITE: relee el store actual,
    mergea `perfiles` por usuario y por espacio (nunca replace a ciegas),
    conserva las claves top-level desconocidas del envelope (futuro metadata)
    y reescribe con tmp + ``os.replace``. El directorio padre (``.saman/``) se
    crea lazy bajo lock (``os.makedirs(dirname, exist_ok=True)``) — nunca en
    lectura. Dos Nuke/renders paralelos no pierden perfiles ajenos.
    """
    if not isinstance(perfiles, dict):
        raise ValueError("perfiles debe ser un objeto JSON")
    with _lock_perfiles(path):
        envelope = _leer_envelope(path)
        actual = envelope.get("perfiles")
        if not isinstance(actual, dict):
            actual = {}
        for user, perfil in perfiles.items():
            _mezclar_perfil_usuario(actual, user, perfil)
        _escribir_perfiles(path, actual)


def _escribir_perfiles(path, perfiles):
    """Envuelve el dict interno en el envelope y escribe ATOMICO (D1/D3).

    Conserva las claves top-level desconocidas (futuro metadata: ``version``,
    ``proyecto``...). NO adquiere lock: el caller debe invocarla BAJO
    ``_lock_perfiles`` (read-merge-write exclusivo, D3) o garantizar por otro
    medio la ausencia de escritores concurrentes.
    """
    envelope = _leer_envelope(path)
    envelope["perfiles"] = perfiles
    _escribir_atomico(path, json.dumps(envelope, ensure_ascii=False, indent=2))


# --- Perfil default -------------------------------------------------------------


def _so_por_forma(base):
    """SO cuyo slot rellena la base inyectada por su forma (AD1/D3)."""
    if base.startswith("/Volumes/"):
        return "macOS"
    if re.match(r"^[A-Za-z]:", base):
        return "Windows"
    if base.startswith("/mnt/"):
        return "Linux"
    return None


def crear_perfil_default(base=None):
    """Construye el perfil 3x3 ficticio por defecto (AD1/D3).

    Tres espacios x tres SO, todos con raices ficticias del proyecto ficticio
    ``CINE``. Una base inyectada rellena SOLO el slot del SO que coincide con
    su forma (``/Volumes/`` → macOS, ``^[A-Za-z]:`` → Windows, ``/mnt/`` →
    Linux) en los TRES espacios: ``{base}/{ESPACIO}``. Si ninguna forma
    coincide se conservan las tres raices ficticias.
    """
    perfil = {}
    for espacio in _ESPACIOS:
        perfil[espacio] = {}
        for so, raiz in _RAICES_FICTICIAS.items():
            perfil[espacio][so] = f"{raiz}/{_PROYECTO_FICTICIO}/{espacio}"
    if base is None:
        return perfil
    base = str(base).strip().rstrip("/")
    so_base = _so_por_forma(base)
    if so_base:
        for espacio in _ESPACIOS:
            perfil[espacio][so_base] = f"{base}/{espacio}"
    return perfil


def ruta_para_espacio(perfil, espacio, so):
    """Root del ``espacio`` para la plataforma ``so``; ``None`` si no (AD1).

    ``perfil`` es un dict 3x3 (espacio → {OS → root}). Combinacion ausente →
    ``None`` sin lanzar (``perfil.get(espacio, {}).get(so)``).
    """
    if not isinstance(perfil, dict):
        return None
    raices = perfil.get(espacio)
    if not isinstance(raices, dict):
        return None
    return raices.get(so)


# --- G6: resolucion por usuario (AD2) + onboarding bajo lock (D3) ---------------


def resolver_perfil(user, path):
    """Resuelve el perfil por USUARIO; desconocido/legacy -> onboarding (spec).

    ``perfiles.get(user)`` directo, sin escalera ni hostname (AD2). Match con
    forma nueva → ese dict 3x3 tal cual. Ausente o con forma legacy → re-
    onboarding via ``asegurar_perfil`` bajo lock (la escritura regenera la
    forma nueva, AD1). NUNCA lanza por desconocido y NUNCA devuelve ``None``.
    """
    perfil = leer_perfiles(path).get(user)
    if detectar_forma_perfil(perfil) == "nuevo":
        return perfil
    return asegurar_perfil(user, path)


def asegurar_perfil(user, path, base=None):
    """Onboarding: crea y persiste el perfil 3x3 bajo lock; sin raise (spec).

    D3: bajo ``_lock_perfiles`` RELEE el store y RE-DETECTA. Si entre nuestra
    lectura inicial y la adquisicion del lock otro proceso ya persisitió un
    perfil NUEVO para el usuario (carrera ganada) devuelve el del ganador SIN
    escribir. Si no: mergea la forma 3x3 por usuario (AD1: una entrada legacy
    se reemplaza) y escribe atomico conservando las claves top-level del
    envelope. Una base inyectada rellena el slot que coincide con su forma
    (``crear_perfil_default(base)``). Sin interaccion de usuario; nunca raise.
    """
    perfil_nuevo = crear_perfil_default(base)
    with _lock_perfiles(path):
        store = leer_perfiles(path)
        existente = store.get(user)
        if detectar_forma_perfil(existente) == "nuevo":
            return existente
        _mezclar_perfil_usuario(store, user, perfil_nuevo)
        _escribir_perfiles(path, store)
    return perfil_nuevo


def renombrar_perfil_store(path, nombre_viejo, nombre_nuevo):
    """Renombra una clave de perfil bajo lock (READ-RENAME-WRITE atomico).

    Re-key de un perfil conservando SUS 9 raices (3 espacios x 3 SO) y el
    resto del store intacto. La validacion (viejo ausente / nuevo ya tomado)
    se hace BAJO el lock sobre el store ACTUAL (D3: no sobre una lectura
    previa, para no decidir con datos stale). Escribe con tmp + ``os.replace``.
    Devuelve el dict interno ``perfiles`` resultado.
    """
    with _lock_perfiles(path):
        store = leer_perfiles(path)
        if nombre_viejo not in store:
            raise ValueError(f"No existe el perfil '{nombre_viejo}' en el store")
        if nombre_nuevo in store:
            raise ValueError(f"Ya existe un perfil llamado '{nombre_nuevo}'")
        perfil = store.pop(nombre_viejo)
        store[nombre_nuevo] = perfil
        _escribir_perfiles(path, store)
    return store


# --- G7: Relativizacion / contexto / entorno (D4/D5) --------------------------

_TOK_PROJECT_ROOT = "[getenv PROJECT_ROOT]"


def _normalizar_para_comparar(path):
    r"""Copia canonica para comparaciones D5 (una cadena, no una tupla).

    ``\`` → ``/``, strip, ``rstrip("/")`` y ``.lower()`` de TODA la cadena.
    Las unicas transformaciones no length-preserving (strip/rstrip) se aplican
    por igual al original normalizado usado para emitir, asi el slice por
    longitud queda consistente. Jamas se compara contra cadenas crudas sin
    normalizar (precondicion de seguridad Windows de la spec).
    """
    return str(path).replace("\\", "/").strip().rstrip("/").lower()


def relativizar(ruta_absoluta, base):
    """Convierte una ruta bajo ``base`` en '[getenv PROJECT_ROOT]/<rel>' (D5).

    Pura de strings, sin filesystem. Two-track: el guard de prefijo
    ``startswith(clave_base + "/")`` se evalúa sobre la copia canonica
    case-folded (drive y volumen case-insensitive) e incluye el ``"/"`` final
    para rechazar prefijos parciales (``/Volumes/estudio2026/...`` bajo base
    ``/Volumes/estudio/2026``). La emision trocea el ORIGINAL normalizado a
    slashes con casing intacto en ``len(base_s)`` — toda transformacion es
    length-preserving, asi el resto conserva su casing (``CINE/TO_VFX`` no se
    degrada a ``cine/to_vfx``). Fuera de la base → sin cambios.
    """
    ruta_s = str(ruta_absoluta).replace("\\", "/").strip().rstrip("/")
    base_s = str(base).replace("\\", "/").strip().rstrip("/")
    clave = ruta_s.lower()
    clave_base = base_s.lower()
    if clave.startswith(clave_base + "/"):
        resto = ruta_s[len(base_s):].lstrip("/")
        return f"{_TOK_PROJECT_ROOT}/{resto}"
    return ruta_s


def absolutizar(ruta, base):
    """Expande '[getenv PROJECT_ROOT]' a la base inyectada VERBATIM (D5).

    Sustituye el token por ``base`` tal cual fue inyectada (casing original de
    drive, slashes forward) — nunca por una copia normalizada y nunca a partir
    de una base deducida. Sin token → la ruta normalizada a slashes, sin
    cambios. El output usa forward slashes (contrato round-trip Windows).
    """
    ruta_s = str(ruta).replace("\\", "/").strip()
    base_s = str(base).replace("\\", "/").strip().rstrip("/")
    if ruta_s.startswith(_TOK_PROJECT_ROOT):
        resto = ruta_s[len(_TOK_PROJECT_ROOT):].lstrip("/")
        if not resto:
            return base_s
        return f"{base_s}/{resto}"
    return ruta_s


def _espacio_prefijado(perfil, ruta_plato):
    """Primer espacio del perfil cuya root (en su SO) prefija el plato (D4).

    Compara sobre la copia canonica (D5) en orden canonico de espacios
    (TO_VFX, COMP, FROM_VFX) y plataformas (macOS, Windows, Linux) y devuelve
    ``(espacio, so)`` de la PRIMERA root que prefija la ruta del plato. Sin
    match → ``(None, None)``. El guard de prefijo parcial rechaza roots como
    ``/Volumes/estudio2026`` (mismo criterio que ``_base_prefijada`` V1).
    """
    if not isinstance(perfil, dict):
        return None, None
    clave_ruta = _normalizar_para_comparar(ruta_plato)
    for espacio in _ESPACIOS:
        raices = perfil.get(espacio)
        if not isinstance(raices, dict):
            continue
        for so in _PLATAFORMAS_SOPORTADAS:
            root = raices.get(so)
            if root is None:
                continue
            clave_root = _normalizar_para_comparar(root)
            if clave_ruta.startswith(clave_root + "/"):
                return espacio, so
    return None, None


def _proyecto_desde_nombre(ruta_plato):
    """Primer token del nombre del plato (fallback determinista, D4)."""
    ruta_s = str(ruta_plato or "").replace("\\", "/")
    basename = ruta_s.rsplit("/", 1)[-1]
    tallo = basename.rsplit(".", 1)[0] if "." in basename else basename
    token = tallo.split("_", 1)[0]
    return token or None


def get_context(perfil, ruta_plato):
    """Contexto ``{proyecto, plano, version, carpeta_salida, espacio, so,
    project_root}`` (D4/AD3).

    Derivado SOLO de perfil y plato inyectados; inputs identicos → outputs
    identicos. ``project_root`` = CORTE ESTRUCTURAL del plato
    (``raiz_proyecto_desde_ruta``); ``espacio``/``so`` salen de la root del
    espacio que prefija el plato (``_espacio_prefijado``); ``proyecto`` es el
    segmento de proyecto de ese corte con fallback al token del nombre del
    plato. ``carpeta_salida`` es SIEMPRE '[getenv PROJECT_ROOT]/COMP/' (AD3).
    Nombres/versiones malformados nunca lanzan (parseo nunca raise).
    """
    espacio, so = _espacio_prefijado(perfil, ruta_plato)
    project_root = raiz_proyecto_desde_ruta(ruta_plato)
    parsed = parsear_plato(ruta_plato)
    plano = parsed.get("plano") if parsed else None
    version = parsed.get("version") if parsed else None

    proyecto = None
    if project_root:
        ultimo = project_root.rsplit("/", 1)[-1]
        if ultimo:
            proyecto = ultimo
    if proyecto is None and parsed and parsed.get("proyecto"):
        proyecto = parsed["proyecto"]
    if proyecto is None:
        proyecto = _proyecto_desde_nombre(ruta_plato)

    carpeta_salida = None
    if proyecto:
        carpeta_salida = f"{_TOK_PROJECT_ROOT}/COMP/"
    return {
        "proyecto": proyecto,
        "plano": plano,
        "version": version,
        "carpeta_salida": carpeta_salida,
        "espacio": espacio,
        "so": so,
        "project_root": project_root,
    }


def variables_entorno(contexto, perfil=None):
    """Contrato de entorno TCL como DATOS; nunca muta os.environ (AD7/spec).

    ``PROJECT_ROOT`` = raiz de proyecto por corte estructural del contexto
    (NUNCA base). PYTHON_TO_VFX / PYTHON_COMP / PYTHON_FROM_VFX = raices del
    perfil para el SO del contexto; si el espacio falta, cae al fallback
    HERMANO ``reconstruir_rutas(dirname, basename)`` de la propia raiz de
    proyecto (contrato de knob V1 intacto) SIN slash final. Clave irresoluble
    → OMITIDA, nunca ``""`` (AD7). ``os.environ`` nunca se toca: la inyeccion
    real (para el TCL ``[getenv PROJECT_ROOT]`` de Nuke via addOnScriptLoad)
    la hace la capa de carga.
    """
    if not isinstance(contexto, dict):
        return {}
    env = {}
    project_root = contexto.get("project_root")
    if project_root:
        env["PROJECT_ROOT"] = str(project_root).replace("\\", "/").strip().rstrip("/")
    so = contexto.get("so")
    if so not in _PLATAFORMAS_SOPORTADAS:
        return env
    perfil = perfil if isinstance(perfil, dict) else None

    # Fallback hermano (AD7): reconstruir_rutas(dirname, basename) del corte.
    reconstruidas = None
    if project_root:
        raiz = str(project_root).replace("\\", "/").strip().rstrip("/")
        if raiz and raiz != "/":
            base, _, proy = raiz.rpartition("/")
            if base and proy:
                reconstruidas = reconstruir_rutas(base, proy)
    claves_knob = {
        "TO_VFX": "TO_VFX_SERVER_",
        "COMP": "comp_SERVER_",
        "FROM_VFX": "FROM_VFX_SERVER_",
    }
    suf = sufijo_so(so)
    for espacio in _ESPACIOS:
        root = None
        if perfil is not None:
            raices = perfil.get(espacio)
            if isinstance(raices, dict):
                root = raices.get(so)
        if root is None and reconstruidas is not None:
            root = reconstruidas.get(claves_knob[espacio] + suf)
        if root:
            env["PYTHON_" + espacio] = str(root).replace("\\", "/").strip().rstrip("/")
    return env


# --- Lock (D6) ------------------------------------------------------------------


class _LockFcntl:
    """Lock exclusivo POSIX con ``fcntl.lockf`` (LOCK_EX | LOCK_NB).

    ``fcntl`` solo existe en POSIX: se importa de forma diferida dentro de los
    metodos para que el modulo cargue igual en Windows (donde la rama nunca se
    instancia).
    """

    def __init__(self, fd):
        self._fd = fd

    def intentar(self):
        import fcntl

        try:
            fcntl.lockf(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def liberar(self):
        import fcntl

        fcntl.lockf(self._fd, fcntl.LOCK_UN)


class _LockMsvcrt:
    """Lock exclusivo Windows con ``msvcrt.locking`` (LK_NBLCK).

    ``msvcrt`` solo existe en Windows: import diferido, igual que fcntl. Antes
    de bloquear se asegura que el archivo tenga al menos 1 byte (seek(0) + pad),
    requisito de ``msvcrt.locking``.
    """

    def __init__(self, fd):
        import msvcrt

        self._msvcrt = msvcrt
        self._fd = fd
        fd.seek(0, os.SEEK_END)
        if fd.tell() == 0:
            fd.write(b"\x00")
            fd.flush()

    def intentar(self):
        try:
            self._fd.seek(0)
            self._msvcrt.locking(self._fd, self._msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def liberar(self):
        self._fd.seek(0)
        self._msvcrt.locking(self._fd, self._msvcrt.LK_UNLCK, 1)


class _LockNoop:
    """No-op documentado para plataformas sin fcntl ni msvcrt (D6).

    Degradado aceptado: ``os.replace`` previene lecturas desgarradas; solo se
    pierden actualizaciones cruzadas entre procesos (last-writer-wins).
    """

    def __init__(self, fd):
        self._fd = fd

    def intentar(self):
        return True

    def liberar(self):
        pass


def _lock_clase(plataforma):
    """Factory de la clase de lock segun plataforma inyectada (D6).

    Acepta nombres estilo ``os.name`` ("posix"/"nt") y estilo
    ``platform.system()`` ("darwin"/"linux"/"windows"). Cualquier otra
    plataforma obtiene el no-op documentado.
    """
    p = (plataforma or "").lower()
    if p in ("posix", "darwin", "linux", "unix"):
        return _LockFcntl
    if p in ("nt", "windows", "win32"):
        return _LockMsvcrt
    return _LockNoop


def _adquirir_lock(lock):
    """Espera el lock con reintentos; agotados → ``TimeoutError`` (D6).

    Cada intento sondea cada ``_PERIODO_POLL_S`` dentro de un plazo de
    ``_PLAZO_INTENTO_S``; si se agotan los ``_INTENTOS_LOCK`` intentos se lanza
    TimeoutError en vez de sobrescribir silenciosamente.
    """
    for _ in range(_INTENTOS_LOCK):
        if _intentar_con_plazo(lock):
            return
    raise TimeoutError(MENSAJE_LOCK_AGOTADO)


def _intentar_con_plazo(lock):
    """Un intento de adquisicion: poll cada ``_PERIODO_POLL_S`` hasta el plazo."""
    limite = time.monotonic() + _PLAZO_INTENTO_S
    while time.monotonic() < limite:
        if lock.intentar():
            return True
        time.sleep(_PERIODO_POLL_S)
    return False


@contextlib.contextmanager
def _lock_perfiles(path, plataforma=None):
    """Context manager de lock exclusivo sobre ``path + ".lock"`` (D6).

    Nunca bloquea el propio ``path``: ``os.replace`` cambia su inode y un lock
    sobre el target quedaria huerfano tras la primera escritura; el archivo
    hermano es estable entre reemplazos. Readers nunca lockean: el replace
    atomico les garantiza ver un inode completo. El directorio padre
    (``.saman/``) se crea lazy AQUI — solo las escrituras adquieren lock, asi
    que nunca se crea en lectura (AD6).
    """
    clase = _lock_clase(plataforma or os.name)
    ruta_lock = path + ".lock"
    directorio = os.path.dirname(os.path.abspath(ruta_lock)) or "."
    os.makedirs(directorio, exist_ok=True)
    with open(ruta_lock, "a+b") as fd:
        lock = clase(fd)
        _adquirir_lock(lock)
        try:
            yield
        finally:
            lock.liberar()