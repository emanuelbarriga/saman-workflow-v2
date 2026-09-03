"""
SamanTools.core.rutas_engine - Motor de rutas de composicion V2 (slice G5).

Parte 1 del motor: STORE de perfiles JSON + LOCK (esquema D1, lock D6 del
diseno). Este archivo implementa SOLO esa parte:

  - ``leer_perfiles`` / ``guardar_perfiles``: store ``nuke_profiles.json`` con
    envelope ``{"perfiles": {usuario: {"hosts": {host: roots}, "default": roots}}}``.
    Escritura ATOMICA (temporal en el mismo directorio + ``os.replace``) y, bajo
    lock, READ-MERGE-WRITE por usuario: nunca se reemplaza a ciegas el perfil de
    otro usuario ni hosts ya conocidos.
  - ``crear_perfil_default``: roots ficticias por plataforma con slotting por
    forma de la base inyectada (``/Volumes/`` → macOS, ``^[A-Za-z]:`` → Windows,
    ``/mnt/`` → Linux; si ninguna coincide, se conservan las tres ficticias).
  - ``_lock_perfiles``: context manager de lock EXCLUSIVO sobre un archivo
    HERMANO ``path + ".lock"`` — nunca el target: ``os.replace`` cambia el inode
    del target y un lock ahi quedaria huerfano tras la primera escritura.
    fcntl (POSIX) / msvcrt (Windows) / no-op documentado; 3 intentos de <=2.0 s
    y TimeoutError al agotar (nunca overwrite silencioso).
  - ``_lock_clase``: factory con plataforma inyectada para testear ambas ramas
    (fcntl y msvcrt) en cualquier maquina de desarrollo.

La resolucion por precedencia, el onboarding y la relativizacion (G6/G7) vienen
en slices posteriores; este modulo queda autocontenido y 100% stdlib. Ninguna
ruta real del estudio: solo raices ficticias ``/Volumes/estudio/2026``,
``L:/VFX/2026`` y ``/mnt/estudio/2026``.
"""

import contextlib
import json
import os
import re
import tempfile
import time

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
        envelope["perfiles"] = actual
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