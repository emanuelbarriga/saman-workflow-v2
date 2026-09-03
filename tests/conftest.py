"""Configuracion minima de pytest para SamanTools V2.

Solo expone la raiz del repositorio en ``sys.path`` para que los tests puedan
importar ``SamanTools``. A proposito NO se define ningun stub de nuke: el
nucleo es puro y la suite debe correr en maquinas sin Nuke instalado.
"""

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))