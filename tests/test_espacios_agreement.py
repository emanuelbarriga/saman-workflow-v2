"""Acuerdo de espacios canonicos entre los cuatro modulos (espacios-extra, PR 5).

Verifica que ``rutas_engine``, ``injector``, ``path_manager`` y
``path_manager_panel`` definen el MISMO conjunto canonico
``{"TO_VFX", "COMP", "FROM_VFX"}`` (spec core-rutas-engine: "Canonical space
definitions agreement"). ``entorno.PREFIJOS`` queda EXCLUIDO del acuerdo: su
prefijo medio es deliberadamente V1 (``"comp"`` en minuscula — el knob del
nodo Rutas es ``comp_SERVER_*``) y NO representa el trio canonico V2
(``PYTHON_COMP``); si entrara al acuerdo, el conjunto diferia del esperado.

El panel importa PySide (dual PySide2->PySide6 con tercer brazo ``None``):
su import se envuelve en un guard ``try/except ImportError`` + ``pytest.skip``
(convencion del archivo de tests del panel) para que el acuerdo corra
headless — solo lee la constante ``_ESPACIOS``, nunca construye widgets.
"""

import pytest

from SamanTools.core import entorno
from SamanTools.core import rutas_engine
from SamanTools.ui import injector
from SamanTools.ui import path_manager

# Guard PySide del panel (convencion test_path_manager_panel): sin PySide
# instalado el modulo no puede importarse y el acuerdo se salta, nunca falla.
try:
    from SamanTools.ui import path_manager_panel
except ImportError:
    pytest.skip(
        "PySide no disponible: no se puede importar path_manager_panel",
        allow_module_level=True,
    )

ESPACIOS_ESPERADOS = {"TO_VFX", "COMP", "FROM_VFX"}


def test_espacios_canonicos_iguales_en_los_cuatro_modulos():
    """Spec: los cuatro modulos definen el MISMO conjunto canonico."""
    conjuntos = {
        frozenset(rutas_engine._ESPACIOS),
        frozenset(injector._ESPACIOS_INYECTOR),
        frozenset(path_manager._ESPACIOS),
        frozenset(path_manager_panel._ESPACIOS),
    }
    assert len(conjuntos) == 1
    assert conjuntos.pop() == frozenset(ESPACIOS_ESPERADOS)


def test_entorno_prefijos_v1_excluido_del_acuerdo():
    """``entorno.PREFIJOS`` NO participa: su prefijo medio es V1 (``comp``)."""
    # V1-casing deliberado: "comp" en minuscula, a diferencia del trio V2
    # (PYTHON_COMP). Documenta POR QUE la exclusion es parte del acordo.
    assert entorno.PREFIJOS == ("TO_VFX", "comp", "FROM_VFX")
    assert "comp" in entorno.PREFIJOS
    assert "COMP" not in entorno.PREFIJOS
    assert set(entorno.PREFIJOS) != ESPACIOS_ESPERADOS