"""
INSTALADOR DE SAMANTOOLS V2 — para el Script Editor de Nuke.

COMO USAR (instalacion / reinstalacion / actualizacion):
  1. Abre Nuke -> Script Editor (View > Script Editor o tecla W).
  2. Pega TODO este codigo y ejecuta con Ctrl+Enter.
  3. Cuando veas el mensaje de exito, reinicia Nuke.

Qué hace (3 estados, como V1):
  - Checkout git completo en ~/.nuke/SamanTools -> consulta la version instalada
    vs la remota (fetch-only, no modifica nada) y, SOLO con tu consentimiento,
    aplica `git pull --ff-only`.
  - Carpeta existente sin .git (instalacion vieja por-copia) -> con tu
    consentimiento, la respalda y la reemplaza con un clon limpio.
  - Sin carpeta -> clona limpio a un temporal y lo renombra (nunca deja un
    checkout parcial).
  - Siempre copia el bootstrap a ~/.nuke/menu.py.

Nunca fuerzo una actualizacion al pegar el script: cada accion pide
consentimiento (nuke.ask / nuke.message) y solo corre dentro de Nuke.

Este archivo separa la logica pura (funciones que reciben paths/URL por
parametro, sin importar nuke) de la capa de consentimiento. Asi la logica
se puede testear headless (sin Nuke instalado): `import nuke` ocurre SOLO
dentro de las funciones de dialogo, nunca a nivel de modulo.

Este archivo es la fuente de verdad; se pega directamente desde el repo.
"""

import os
import shutil
import subprocess
import time

REPO_URL = "https://github.com/emanuelbarriga/saman-workflow-v2.git"
BRANCH = "main"
NUKE_DIR = os.path.expanduser("~/.nuke")
TOOLS_DIR = os.path.join(NUKE_DIR, "SamanTools")
MENU_DEST = os.path.join(NUKE_DIR, "menu.py")
BOOTSTRAP_ORIGEN = os.path.join(TOOLS_DIR, "bootstrap", "menu.py")


# --- Logica pura (testeable sin Nuke) ----------------------------------------


def _ejecutar_git(args, cwd=None, timeout=180):
    """Ejecuta git silenciosamente. Devuelve True si el returncode es 0.

    Nunca lanza: ante cualquier fallo (sin git, sin red) devuelve False.
    """
    try:
        resultado = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return resultado.returncode == 0
    except Exception:
        return False


def _salida_git(args, cwd=None, timeout=60):
    """Ejecuta git capturando la salida. Devuelve (returncode, stdout, stderr)."""
    try:
        resultado = subprocess.run(
            args, cwd=cwd, capture_output=True, timeout=timeout
        )
        return resultado.returncode, resultado.stdout, resultado.stderr
    except Exception:
        return -1, b"", b""


def _estado_destino(destino):
    """Clasifica un destino en 3 estados.

    - "checkout_git": existe una carpeta con .git (instalacion por git).
    - "copia_antigua": existe una carpeta sin .git (instalacion vieja por-copia).
    - "sin_checkout": no existe la carpeta.
    """
    if os.path.isdir(destino):
        if os.path.isdir(os.path.join(destino, ".git")):
            return "checkout_git"
        return "copia_antigua"
    return "sin_checkout"


def _clonar_limpio(repo_url, destino, branch="main", timeout=180):
    """Clona a un temporal hermano y lo renombra al destino.

    Patron "clonar limpio" de V1: nunca se clona directo a una carpeta que
    ya existe. El temporal vive junto al destino (misma carpeta padre), asi
    el rename es atomico en el mismo volumen. Si el clone falla, el temporal
    se elimina y el destino queda intacto. Devuelve True si el checkout
    quedo en el destino.
    """
    padre = os.path.dirname(destino)
    os.makedirs(padre, exist_ok=True)
    temporal = os.path.join(
        padre, ".saman_clone_tmp_" + time.strftime("%Y%m%d%H%M%S")
    )
    clonado = _ejecutar_git(
        ["git", "clone", "--depth", "1", "--branch", branch, repo_url, temporal],
        timeout=timeout,
    )
    if not clonado:
        shutil.rmtree(temporal, ignore_errors=True)
        return False
    shutil.rmtree(destino, ignore_errors=True)
    os.rename(temporal, destino)
    return True


def _pull_ff_only(repo_dir, timeout=120):
    """Actualiza un checkout con `git pull --ff-only`. Devuelve True si fue exitoso.

    Fast-forward puro: si la rama local divergio, git rechaza el pull y no
    modifica nada.
    """
    return _ejecutar_git(
        ["git", "pull", "--ff-only", "--quiet"], cwd=repo_dir, timeout=timeout
    )


def _copiar_bootstrap(origen_bootstrap, destino_bootstrap):
    """Copia el bootstrap del checkout a ~/.nuke/menu.py.

    Devuelve True si el archivo quedo copiado en el destino; False si el
    origen no existe o la copia fallo.
    """
    if not os.path.isfile(origen_bootstrap):
        return False
    try:
        os.makedirs(os.path.dirname(destino_bootstrap), exist_ok=True)
        shutil.copy2(origen_bootstrap, destino_bootstrap)
        return True
    except Exception:
        return False


def _hay_version_nueva(repo_dir, branch, timeout=120):
    """Consulta si origin/<branch> avanzo respecto del HEAD local.

    Solo hace git fetch (no modifica el checkout). Devuelve True si hay
    version nueva, False si esta al dia y None si la consulta fallo (sin
    red, sin git, etc.).
    """
    codigo, _, _ = _salida_git(
        ["git", "fetch", "origin", branch], cwd=repo_dir, timeout=timeout
    )
    if codigo != 0:
        return None
    _, head, _ = _salida_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, timeout=15)
    _, origin, _ = _salida_git(
        ["git", "rev-parse", "origin/" + branch], cwd=repo_dir, timeout=15
    )
    if not head or not origin:
        return None
    return head.strip() != origin.strip()


def _commit_local(repo_dir):
    """Devuelve el hash corto del HEAD local (o "?" si falla)."""
    codigo, salida, _ = _salida_git(
        ["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, timeout=15
    )
    if codigo != 0:
        return "?"
    return salida.decode(errors="replace").strip()


def _version_instalada(repo_dir):
    """Devuelve (version, commit) del checkout instalado.

    - version: __version__ de SamanTools/__init__.py (SemVer del repo).
    - commit: hash corto de HEAD — la senal fiel de qué codigo está cargado.
    Ante cualquier fallo devuelve ("desconocida", ...). Nunca lanza.
    """
    version = "desconocida"
    try:
        import importlib.util

        ruta_init = os.path.join(repo_dir, "SamanTools", "__init__.py")
        spec = importlib.util.spec_from_file_location(
            "saman_tools_version_instalador", ruta_init
        )
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        version = getattr(modulo, "__version__", "desconocida")
    except Exception:
        pass
    return version, _commit_local(repo_dir)


# --- Capa Nuke: consentimiento y mensajes (SOLO dentro de Nuke) --------------


def _preguntar(texto):
    """Pide confirmacion con nuke.ask. Solo corre dentro de Nuke."""
    import nuke

    return nuke.ask(texto)


def _avisar(texto):
    """Muestra un mensaje con nuke.message. Solo corre dentro de Nuke."""
    import nuke

    nuke.message(texto)


def _sincronizar_bootstrap():
    """Copia el bootstrap a ~/.nuke/menu.py y avisa si no se encuentra."""
    if _copiar_bootstrap(BOOTSTRAP_ORIGEN, MENU_DEST):
        return True
    _avisar(
        "Instalación incompleta: no se encontró el bootstrap.\n"
        "Probá ejecutar el instalador de nuevo."
    )
    return False


def _instalar_sobre_checkout():
    """Estado checkout_git: compara versiones y actualiza SOLO con consentimiento."""
    nueva = _hay_version_nueva(TOOLS_DIR, BRANCH)
    if nueva is None:
        _avisar(
            "No se pudo consultar la actualización.\n\n"
            "Verificá tu conexión a internet y volvé a ejecutar el instalador."
        )
        return
    if nueva:
        if _preguntar(
            "Hay una nueva versión de SamanTools.\n\n"
            "Instalada (commit %s).\n\n"
            "¿Actualizar ahora?" % _commit_local(TOOLS_DIR)
        ):
            if _pull_ff_only(TOOLS_DIR):
                _sincronizar_bootstrap()
                version, commit = _version_instalada(TOOLS_DIR)
                _avisar(
                    "SamanTools actualizado correctamente.\n\n"
                    "Versión: %s\n"
                    "Commit: %s\n\n"
                    "Reiniciá Nuke para cargar la nueva versión." % (version, commit)
                )
            else:
                _avisar(
                    "No se pudo actualizar SamanTools.\n"
                    "Verificá tu conexión a internet."
                )
        else:
            _avisar("No se actualizó: seguís trabajando con la versión instalada.")
    else:
        _sincronizar_bootstrap()
        version, commit = _version_instalada(TOOLS_DIR)
        _avisar(
            "Ya tenés la última versión de SamanTools.\n\n"
            "Versión: %s\n"
            "Commit: %s\n\n"
            "Tu copia instalada está al día con GitHub." % (version, commit)
        )


def _instalar_sobre_copia_vieja():
    """Estado copia_antigua: respalda y reinstala con un clon limpio."""
    if not _preguntar(
        "Hay una instalación vieja de SamanTools (por copia, sin git).\n\n"
        "Se la va a respaldar en la misma carpeta y reinstalar desde GitHub.\n\n"
        "¿Continuar?"
    ):
        return
    respaldo = TOOLS_DIR + ".prev_" + time.strftime("%Y%m%d%H%M%S")
    try:
        os.rename(TOOLS_DIR, respaldo)
    except Exception:
        _avisar("No se pudo respaldar la instalación actual.\nNo se hizo ningún cambio.")
        return
    if _clonar_limpio(REPO_URL, TOOLS_DIR):
        _sincronizar_bootstrap()
        _avisar(
            "SamanTools instalado correctamente.\n\n"
            "La versión vieja quedó respaldada y reiniciá Nuke."
        )
    else:
        _avisar(
            "No se pudo descargar el repositorio.\n"
            "La instalación anterior quedó respaldada como:\n%s" % respaldo
        )


def _instalar_desde_cero():
    """Estado sin_checkout: clona limpio (temporal + rename) y copia el bootstrap."""
    if not _preguntar(
        "SamanTools no está instalado en este equipo.\n\n"
        "¿Descargar la última versión desde GitHub?"
    ):
        return
    if _clonar_limpio(REPO_URL, TOOLS_DIR):
        _sincronizar_bootstrap()
        _avisar(
            "SamanTools instalado correctamente.\n\n"
            "Reiniciá Nuke para que aparezca el menú SamanTools."
        )
    else:
        _avisar(
            "No se pudo descargar el repositorio.\n"
            "Verificá la conexión a internet y que Git esté instalado."
        )


def instalar_script_editor():
    """Entry point principal: detecta estado, pide consentimiento y aplica.

    Solo corre dentro de Nuke (las funciones de dialogo importan nuke);
    al importar el modulo no se ejecuta nada (guard de __main__).
    """
    if shutil.which("git") is None:
        _avisar(
            "Git no está instalado en este equipo.\n\n"
            "Descargalo de https://git-scm.com/downloads\n"
            "y volvé a ejecutar el instalador."
        )
        return

    os.makedirs(NUKE_DIR, exist_ok=True)
    estado = _estado_destino(TOOLS_DIR)

    if estado == "checkout_git":
        _instalar_sobre_checkout()
    elif estado == "copia_antigua":
        _instalar_sobre_copia_vieja()
    else:
        _instalar_desde_cero()


if __name__ == "__main__":
    instalar_script_editor()