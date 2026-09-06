"""
DESINSTALADOR DE SAMANTOOLS V2 — para el Script Editor de Nuke.

COMO USAR (desinstalacion definitiva):
  1. Abre Nuke -> Script Editor (View > Script Editor o tecla W).
  2. Pega TODO este codigo y ejecuta con Ctrl+Enter.
  3. Cuando veas el mensaje de exito, reinicia Nuke.

Qué hace (espejo del instalador, patron V1):
  - Borra el checkout ~/.nuke/SamanTools y cualquier respaldo
    ~/.nuke/SamanTools.desinstalado_* de ciclos previos.
  - Borra el bootstrap ~/.nuke/menu.py SOLO si lleva el marcador V2
    ("SamanTools V2 bootstrap"). Un menu.py ajeno o el de V1 se deja
    intacto: la coexistencia temporal no se rompe.
  - Los nodos ya insertados en proyectos NO se borran (pero el widget
    global del Breakdown dejara de estar disponible en equipos sin el
    paquete).

Nunca fuerzo nada al pegar el script: pide consentimiento (nuke.ask /
nuke.message) y solo corre dentro de Nuke.

Este archivo separa la logica pura (funciones que reciben paths por
parametro, sin importar nuke) de la capa de consentimiento. Asi la logica
se puede testear headless (sin Nuke instalado): `import nuke` ocurre SOLO
dentro de las funciones de dialogo, nunca a nivel de modulo.

Este archivo es la fuente de verdad; se pega directamente desde el repo.
"""

import os
import shutil

NUKE_DIR = os.path.expanduser("~/.nuke")
TOOLS_DIR = os.path.join(NUKE_DIR, "SamanTools")
MENU_DEST = os.path.join(NUKE_DIR, "menu.py")
MARCADOR = "SamanTools V2 bootstrap"


# --- Logica pura (testeable sin Nuke) ----------------------------------------


def _limpiar_checkout_y_respaldos(padre, nombre):
    """Borra el checkout `nombre` y sus respaldos `nombre.desinstalado_*`.

    `padre` es la carpeta que contiene el checkout (en vivo: ~/.nuke).
    Devuelve una lista de mensajes por cada elemento eliminado. Nunca lanza:
    ante un error devuelve el mensaje de fallo sin abortar el resto.
    """
    hechos = []
    try:
        for item in os.listdir(padre):
            if item == nombre or item.startswith(nombre + ".desinstalado_"):
                ruta = os.path.join(padre, item)
                shutil.rmtree(ruta, ignore_errors=True)
                hechos.append("Eliminado: %s" % item)
    except Exception as e:
        hechos.append("No se pudo limpiar la carpeta: %s" % e)
    return hechos


def _borrar_bootstrap_si_marcador(menu_path, marcador):
    """Borra menu.py SOLO si lleva el marcador V2.

    Un menu.py ajeno (sin el marcador, p. ej. el de V1) se deja intacto.
    Devuelve una lista de mensajes con lo que se hizo o por qué no se toco.
    Nunca lanza.
    """
    hechos = []
    try:
        with open(menu_path, "r") as f:
            contenido = f.read()
    except Exception:
        contenido = ""
    if "SamanTools" in contenido and marcador.lower() in contenido.lower():
        try:
            os.remove(menu_path)
            hechos.append("Eliminado: %s" % os.path.basename(menu_path))
        except Exception as e:
            hechos.append("No se pudo borrar el bootstrap: %s" % e)
    elif os.path.isfile(menu_path):
        hechos.append("menu.py NO se toco (no parece ser el bootstrap de SamanTools).")
    return hechos


def _desinstalar(padre, nombre, menu_path, marcador):
    """Operacion pura de desinstalacion definitiva. Devuelve lista de mensajes.

    Es el espejo de `_desinstalar_ahora` del bootstrap V2, sin la capa de
    dialogo: quien llama decide como preguntar y como avisar.
    """
    hechos = _limpiar_checkout_y_respaldos(padre, nombre)
    hechos.extend(_borrar_bootstrap_si_marcador(menu_path, marcador))
    return hechos


# --- Capa Nuke: consentimiento y mensajes (SOLO dentro de Nuke) --------------


def _preguntar(texto):
    """Pide confirmacion con nuke.ask. Solo corre dentro de Nuke."""
    import nuke

    return nuke.ask(texto)


def _avisar(texto):
    """Muestra un mensaje con nuke.message. Solo corre dentro de Nuke."""
    import nuke

    nuke.message(texto)


def desinstalar_script_editor():
    """Entry point principal: pide consentimiento y aplica la desinstalacion.

    Solo corre dentro de Nuke (las funciones de dialogo importan nuke);
    al importar el modulo no se ejecuta nada (guard de __main__).
    """
    if not _preguntar(
        "¿Desinstalar SamanTools?\n\n"
        "Se BORRARÁN todos los archivos de SamanTools de este equipo:\n"
        "  - ~/.nuke/SamanTools (herramientas + respaldos)\n"
        "  - ~/.nuke/menu.py (bootstrap)\n\n"
        "Los nodos ya insertados en proyectos NO se borran.\n\n"
        "¿Confirmás?"
    ):
        return

    hechos = _desinstalar(NUKE_DIR, "SamanTools", MENU_DEST, MARCADOR)

    _avisar(
        "SamanTools desinstalado de este equipo.\n\n"
        + "\n".join(hechos)
        + "\n\nNo queda ningún archivo de SamanTools. Reiniciá Nuke."
    )


if __name__ == "__main__":
    desinstalar_script_editor()