"""
SamanTools.core.rutas_engine - Motor de rutas de composicion V2 (slices G5+G6).

Partes 1 y 2 del motor: STORE de perfiles JSON + LOCK (esquema D1, lock D6) y
RESOLUCION por precedencia + ONBOARDING bajo lock (D2/D3). Este archivo
implementa:

  - ``leer_perfiles`` / ``guardar_perfiles``: store ``nuke_profiles.json`` con
    envelope ``{"perfiles": {usuario: {"hosts": {host: roots}, "default": roots}}}``.
    Escritura ATOMICA (temporal en el mismo directorio + ``os.replace``) y, bajo
    lock, READ-MERGE-WRITE por usuario: nunca se reemplaza a ciegas el perfil de
    otro usuario ni hosts ya conocidos.
  - ``crear_perfil_default``: roots ficticias por plataforma con slotting por
    forma de la base inyectada (``/Volumes/`` → macOS, ``^[A-Za-z]:`` → Windows,
    ``/mnt/`` → Linux; si ninguna coincide, se conservan las tres ficticias).
  - ``_emparejar_perfil``: escalera de precedencia D2 — par exacto
    user+hostname → user-only ``default`` → primer usuario en orden de documento
    con ese hostname → ``None`` (marcador de onboarding; la API publica lo
    absorbe y nunca lo expone).
  - ``resolver_perfil``: lee (sin lock) y empareja; desconocido → onboarding
    via ``asegurar_perfil``. NUNCA lanza por desconocido ni devuelve ``None``.
  - ``asegurar_perfil``: onboarding bajo el lock: relee y re-resuelve (carrera
    ganada → devuelve el perfil del ganador sin reescribir); si no, merge por
    usuario (``hosts[hostname]`` + ``default``) y escritura atomica.
  - ``ruta_para_plataforma``: raiz del perfil para macOS/Windows/Linux; ``None``
    si la plataforma no esta en el perfil (sin raise).
  - ``_lock_perfiles``: context manager de lock EXCLUSIVO sobre un archivo
    HERMANO ``path + ".lock"`` — nunca el target: ``os.replace`` cambia el inode
    del target y un lock ahi quedaria huerfano tras la primera escritura.
    fcntl (POSIX) / msvcrt (Windows) / no-op documentado; 3 intentos de <=2.0 s
    y TimeoutError al agotar (nunca overwrite silencioso).
  - ``_lock_clase``: factory con plataforma inyectada para testear ambas ramas
    (fcntl y msvcrt) en cualquier maquina de desarrollo.

Parte 3 (slices G7): mapeo relativizacion + contexto + entorno:

  - ``relativizar``/``absolutizar`` (D5 two-track): relativizacion string-level
    ``[getenv PROJECT_ROOT]`` — la comparacion de prefijo se hace sobre una
    copia canonica case-folded (backslashes a slashes, strip, ``rstrip("/")``,
    ``.lower()`` total) y la emision trocea el ORIGINAL normalizado a slashes
    con casing intacto. Nunca compara contra cadenas crudas (seguridad
    Windows: ``l:\\vfx\\2026\\...`` ≡ ``L:/VFX/2026``). ``absolutizar``
    sustituye la base inyectada VERBATIM (casing original, slashes forward).
  - ``get_context``: ``{proyecto, plano, version, carpeta_salida, base, so}``
    derivado SOLO de perfil+plato inyectados; ``base`` es la primera root del
    perfil prefijada por la ruta del plato y ``so`` su plataforma; ``proyecto``
    via ``proyecto_desde_ruta(plato, base)`` con fallback al primer token del
    nombre; ``carpeta_salida`` siempre relativa a ``[getenv PROJECT_ROOT]``.
  - ``variables_entorno``: contrato TCL como DATOS (``PROJECT_ROOT`` + 
    PYTHON_TO_VFX/COMP/FROM_VFX derivados de ``reconstruir_rutas`` filtrado por
    ``sufijo_so``). NUNCA muta ``os.environ``: la inyeccion la hace la futura
    capa de carga (addOnScriptLoad), no el motor.

Este modulo queda autocontenido y 100% stdlib, sin ambiente (sin getpass,
socket ni platform en la logica: todo parametro es inyectado).
Ninguna ruta real del estudio: solo raices ficticias ``/Volumes/estudio/2026``,
``L:/VFX/2026`` y ``/mnt/estudio/2026``.
"""

import contextlib
import json
import os
import re
import tempfile
import time

from .entorno import proyecto_desde_ruta, reconstruir_rutas, sufijo_so
from .nombres import parsear_plato

_ROOT_DEF_MACOS = "/Volumes/estudio/2026"
_ROOT_DEF_WINDOWS = "L:/VFX/2026"
_ROOT_DEF_LINUX = "/mnt/estudio/2026"

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
    ...}`` (D1) y este devuelve SOLO el dict interno.
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


# --- Merge por usuario (kernel compartido, D3) ----------------------------------


def _mezclar_perfil_usuario(store, user, perfil):
    """Merge de UN usuario en `store`: hosts por host, default reemplazado.

    Otros usuarios quedan intactos; dentro del usuario, los hosts ya conocidos
    se conservan y solo se agregan/actualizan los entrantes. Devuelve `store`
    (muta in-place: es el kernel de read-merge-write bajo lock).
    """
    if not isinstance(perfil, dict):
        raise ValueError(f"Perfil de '{user}' debe ser un objeto JSON")
    existing = store.get(user)
    if not isinstance(existing, dict):
        existing = {}
        store[user] = existing
    hosts_entrantes = perfil.get("hosts")
    if hosts_entrantes is not None:
        if not isinstance(hosts_entrantes, dict):
            raise ValueError(f"'hosts' del usuario '{user}' debe ser un objeto JSON")
        hosts_dest = existing.get("hosts")
        if not isinstance(hosts_dest, dict):
            hosts_dest = {}
            existing["hosts"] = hosts_dest
        for host, roots in hosts_entrantes.items():
            hosts_dest[host] = roots
    if "default" in perfil:
        existing["default"] = perfil["default"]
    return store


def _merge_perfil(store, user, hostname, roots):
    """Merge de un par user/hostname → roots en un store existente (D3).

    Kernel que el onboarding de G6 usara bajo lock: escribe tanto
    ``hosts[hostname]`` como ``default`` para que el fallback user-only
    funcione en otras maquinas del mismo usuario.
    """
    return _mezclar_perfil_usuario(
        store, user, {"hosts": {hostname: roots}, "default": roots}
    )


def guardar_perfiles(path, perfiles):
    """Persiste el store interno bajo lock y de forma atomica (spec).

    Bajo el lock exclusivo hace READ-MERGE-WRITE: relee el store actual, mergea
    `perfiles` por usuario (nunca replace a ciegas), conserva las claves
    top-level desconocidas del envelope (futuro metadata) y reescribe con tmp +
    ``os.replace``. Dos Nuke/renders paralelos no pierden perfiles ajenos.
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


def crear_perfil_default(base=None):
    """Construye roots ficticias por plataforma (D1/D3).

    Una base inyectada rellena el slot que coincide con su forma:
    ``/Volumes/`` → macOS, ``^[A-Za-z]:`` → Windows, ``/mnt/`` → Linux. Si
    ninguna forma coincide se conservan las tres roots ficticias.
    """
    roots = {
        "macOS": _ROOT_DEF_MACOS,
        "Windows": _ROOT_DEF_WINDOWS,
        "Linux": _ROOT_DEF_LINUX,
    }
    if base is None:
        return roots
    base = str(base).strip()
    if base.startswith("/Volumes/"):
        roots["macOS"] = base
    elif re.match(r"^[A-Za-z]:", base):
        roots["Windows"] = base
    elif base.startswith("/mnt/"):
        roots["Linux"] = base
    return roots


# --- G6: Resolucion por precedencia (D2) + onboarding bajo lock (D3) -----------


def _emparejar_perfil(user, hostname, perfiles):
    """Empareja user/hostname contra el store interno con la precedencia D2.

    Orden canonico: (1) par exacto ``perfiles[user]["hosts"][hostname]`` -> ese
    dict de roots; (2) user-only ``perfiles[user]["default"]`` -> ese dict; (3)
    hostname-only: primer usuario en orden de documento (insercion JSON) cuyo
    ``hosts[hostname]`` exista -> ese dict (estaciones compartidas: maquina
    conocida, usuario no); (4) miss -> ``None``: el marcador de onboarding
    (D2: nunca excepcion; la API publica lo absorbe y nunca lo expone).

    Todo match devuelve el MISMO shape ``{"macOS","Windows","Linux"}`` (D2:
    "full vs partial" es procedencia, no forma). Valores no-dict se ignoran
    (D1: claves internas desconocidas no rompen el motor).
    """
    usuario = perfiles.get(user)
    if isinstance(usuario, dict):
        hosts = usuario.get("hosts")
        if isinstance(hosts, dict):
            roots = hosts.get(hostname)
            if isinstance(roots, dict):
                return roots
        default = usuario.get("default")
        if isinstance(default, dict):
            return default
    for perfil in perfiles.values():
        if not isinstance(perfil, dict):
            continue
        hosts = perfil.get("hosts")
        if not isinstance(hosts, dict):
            continue
        roots = hosts.get(hostname)
        if isinstance(roots, dict):
            return roots
    return None


def ruta_para_plataforma(perfil, so):
    """Raiz del perfil para la plataforma ``so``; ``None`` si no esta (D2).

    ``perfil`` es un dict de roots (shape ``{"macOS","Windows","Linux"}``). Si
    la plataforma pedida no existe en el perfil se devuelve ``None``, sin
    lanzar: la llamada indice via ``perfil.get(so)`` (D2).
    """
    if not isinstance(perfil, dict):
        return None
    return perfil.get(so)


def asegurar_perfil(user, hostname, path, base=None):
    """Onboarding: crea y persiste el perfil default bajo lock; sin raise (spec).

    D3: bajo ``_lock_perfiles`` RELEE el store y RE-RESUELVE. Si el par ya
    existe entre nuestra lectura inicial y la adquisicion del lock (carrera
    ganada por otro proceso) devuelve el perfil del ganador SIN escribir. Si
    no, hace merge por usuario (``hosts[hostname]`` + ``default``, via
    ``_merge_perfil`` — el fallback user-only funciona luego en otras maquinas)
    y escribe atomico conservando las claves top-level del envelope. Una base
    inyectada rellena el slot que coincide con su forma
    (``crear_perfil_default(base)``). Sin interaccion de usuario; nunca raise.
    """
    roots = crear_perfil_default(base)
    with _lock_perfiles(path):
        store = leer_perfiles(path)
        ganador = _emparejar_perfil(user, hostname, store)
        if ganador is not None:
            return ganador
        _merge_perfil(store, user, hostname, roots)
        _escribir_perfiles(path, store)
    return roots


def resolver_perfil(user, hostname, path):
    """Resuelve las roots por precedencia D2; desconocido -> onboarding (spec).

    Lee (sin lock; el replace atomico garantiza un inode completo) y empareja.
    Match -> devuelve ese dict de roots tal cual. Miss (marcador ``None`` de
    ``_emparejar_perfil``) -> ``asegurar_perfil`` bajo lock. NUNCA lanza por
    desconocido y NUNCA devuelve ``None``: el marcador de onboarding es interno
    al emparejador y la API publica lo absorbe (D2/D3).
    """
    match = _emparejar_perfil(user, hostname, leer_perfiles(path))
    if match is not None:
        return match
    return asegurar_perfil(user, hostname, path)


# --- G7: Relativizacion / contexto / entorno (D4/D5) --------------------------

_TOK_PROJECT_ROOT = "[getenv PROJECT_ROOT]"

# Plataformas soportadas para las que existe sufijo de knob (sufijo_so).
_PLATAFORMAS_SOPORTADAS = ("macOS", "Windows", "Linux")


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


def _base_prefijada(perfil, ruta_plato):
    """Primera root del perfil que es prefijo de la ruta del plato (D4).

    Compara sobre la copia canonica (D5) y devuelve la root VERBATIM
    (casing original, slashes forward, sin ``/`` final) junto con su
    plataforma: ``(base, so)``. Sin match → ``(None, None)``. El guard de
    prefijo parcial rechaza roots como ``/Volumes/estudio2026``.
    """
    if not isinstance(perfil, dict):
        return None, None
    clave_ruta = _normalizar_para_comparar(ruta_plato)
    for so, root in perfil.items():
        if root is None:
            continue
        clave_root = _normalizar_para_comparar(root)
        if clave_ruta.startswith(clave_root + "/"):
            root_s = str(root).replace("\\", "/").strip().rstrip("/")
            return root_s, so
    return None, None


def _proyecto_desde_nombre(ruta_plato):
    """Primer token del nombre del plato (fallback determinista, D4).

    Cubre el plato SOLO con basename (sin ruta bajo la base): ni la ruta ni el
    parseo canonical aportan proyecto, y la convencion
    '{PROYECTO}_{EP}_{escena}_{shot}_V{nn}' hace que el prefijo del nombre sea
    el proyecto. Nunca lanza.
    """
    ruta_s = str(ruta_plato or "").replace("\\", "/")
    basename = ruta_s.rsplit("/", 1)[-1]
    tallo = basename.rsplit(".", 1)[0] if "." in basename else basename
    token = tallo.split("_", 1)[0]
    return token or None


def get_context(perfil, ruta_plato):
    """Contexto ``{proyecto, plano, version, carpeta_salida, base, so}`` (D4).

    Derivado SOLO de perfil y plato inyectados; inputs identicos → outputs
    identicos. ``base`` es la primera root del perfil prefijada por la ruta del
    plato y ``so`` su plataforma; ``proyecto`` se deriva con
    ``proyecto_desde_ruta(plato, base)`` (base inyectada, determinista) y, si
    no hay match, cae al primer token del nombre del plato. ``carpeta_salida``
    es siempre relativa a '[getenv PROJECT_ROOT]'. Nombres/versiones
    malformados nunca lanzan (parseo de nombres nunca raise).
    """
    base, so = _base_prefijada(perfil, ruta_plato)
    parsed = parsear_plato(ruta_plato)
    plano = parsed.get("plano") if parsed else None
    version = parsed.get("version") if parsed else None

    proyecto = None
    if base:
        proyecto = proyecto_desde_ruta(ruta_plato, base=base)
    if proyecto is None and parsed and parsed.get("proyecto"):
        proyecto = parsed["proyecto"]
    if proyecto is None:
        proyecto = _proyecto_desde_nombre(ruta_plato)

    carpeta_salida = None
    if proyecto:
        carpeta_salida = f"{_TOK_PROJECT_ROOT}/{proyecto}/COMP/"
    return {
        "proyecto": proyecto,
        "plano": plano,
        "version": version,
        "carpeta_salida": carpeta_salida,
        "base": base,
        "so": so,
    }


def variables_entorno(contexto):
    """Contrato de entorno TCL como DATOS; nunca muta os.environ (D4/spec).

    Devuelve ``{'PROJECT_ROOT': base resuelta}`` y, si hay base, plataforma
    soportada y proyecto, ademas PYTHON_TO_VFX / PYTHON_COMP / PYTHON_FROM_VFX
    derivados de ``reconstruir_rutas(base, proyecto)`` filtrado por
    ``sufijo_so(so)`` (rutas ficticias con forward slashes). Puro data-driven:
    la inyeccion real a ``os.environ`` (para el TCL ``[getenv PROJECT_ROOT]``
    de Nuke via addOnScriptLoad) la hace la futura capa de carga.
    """
    if not isinstance(contexto, dict):
        return {}
    base = contexto.get("base")
    if not base:
        return {}
    so = contexto.get("so")
    proyecto = contexto.get("proyecto")
    env = {"PROJECT_ROOT": str(base)}
    if so in _PLATAFORMAS_SOPORTADAS and proyecto:
        suf = sufijo_so(so)
        rutas = reconstruir_rutas(base, proyecto)
        env["PYTHON_TO_VFX"] = rutas["TO_VFX_SERVER_" + suf]
        env["PYTHON_COMP"] = rutas["comp_SERVER_" + suf]
        env["PYTHON_FROM_VFX"] = rutas["FROM_VFX_SERVER_" + suf]
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
    atomico les garantiza ver un inode completo.
    """
    clase = _lock_clase(plataforma or os.name)
    ruta_lock = path + ".lock"
    with open(ruta_lock, "a+b") as fd:
        lock = clase(fd)
        _adquirir_lock(lock)
        try:
            yield
        finally:
            lock.liberar()