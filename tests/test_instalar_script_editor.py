"""Tests de la logica pura del instalador de Script Editor (V2).

El instalador separa la logica pura (sin Nuke) de la capa de consentimiento
(nuke.ask / nuke.message). Aquí solo se testea la logica pura con monkeypatch
de `subprocess.run` / `shutil` / `os` y `tmp_path`; la parte que usa nuke (0%)
no se testea, patron V1.

Además se incluyen dos guardias anti-fuga: el instalador y el bootstrap no
deben contener el placeholder `TU_USUARIO`, y `import nuke` solo puede
aparecer dentro de funciones (nunca a nivel de modulo).
"""

import os
import re
from pathlib import Path

import instalar_script_editor as instalador

_RAIZ = Path(__file__).resolve().parent.parent


class _ResultadoFalso:
    """Resultado simulado de subprocess.run."""

    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# --- _estado_destino ----------------------------------------------------------


def test_estado_sin_carpeta(tmp_path):
    destino = tmp_path / "SamanTools"
    assert instalador._estado_destino(str(destino)) == "sin_checkout"


def test_estado_carpeta_con_git(tmp_path):
    destino = tmp_path / "SamanTools"
    destino.mkdir()
    (destino / ".git").mkdir()
    assert instalador._estado_destino(str(destino)) == "checkout_git"


def test_estado_carpeta_sin_git(tmp_path):
    destino = tmp_path / "SamanTools"
    destino.mkdir()
    assert instalador._estado_destino(str(destino)) == "copia_antigua"


# --- _clonar_limpio -----------------------------------------------------------


def test_clonar_limpio_clona_a_temporal_y_renombra(tmp_path, monkeypatch):
    destino = str(tmp_path / "SamanTools")
    url = "https://github.com/ejemplo/saman-workflow-v2.git"
    llamadas = []

    def fake_run(args, **kwargs):
        llamadas.append(args)
        if len(args) >= 6 and args[1] == "clone":
            os.makedirs(args[-1])  # simula el clone creando el temporal
        return _ResultadoFalso()

    monkeypatch.setattr(instalador.subprocess, "run", fake_run)

    assert instalador._clonar_limpio(url, destino)

    assert llamadas[0][:5] == ["git", "clone", "--depth", "1", "--branch"]
    assert llamadas[0][5] == "main"
    assert llamadas[0][6] == url
    assert os.path.basename(llamadas[0][-1]).startswith(".saman_clone_tmp_")
    assert os.path.dirname(llamadas[0][-1]) == str(tmp_path)
    # el temporal original ya no existe; el checkout quedo en el destino
    assert os.path.isdir(destino)
    sobras = [p for p in os.listdir(tmp_path) if p.startswith(".saman_clone_tmp_")]
    assert sobras == []


def test_clonar_limpio_limpia_temporal_si_clone_falla(tmp_path, monkeypatch):
    destino = tmp_path / "SamanTools"
    destino.mkdir()

    def fake_run(args, **kwargs):
        if len(args) >= 6 and args[1] == "clone":
            os.makedirs(args[-1])
        return _ResultadoFalso(returncode=1)

    monkeypatch.setattr(instalador.subprocess, "run", fake_run)

    assert not instalador._clonar_limpio("https://github.com/ejemplo.git", str(destino))
    # el destino (instalacion previa) queda intacto y sin temporal suelto
    assert os.path.isdir(str(destino))
    sobras = [p for p in os.listdir(tmp_path) if p.startswith(".saman_clone_tmp_")]
    assert sobras == []


# --- _pull_ff_only ------------------------------------------------------------


def test_pull_ff_only_corre_comando_esperado(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo")
    llamadas = []

    def fake_run(args, **kwargs):
        llamadas.append((args, kwargs))
        return _ResultadoFalso()

    monkeypatch.setattr(instalador.subprocess, "run", fake_run)

    assert instalador._pull_ff_only(repo)
    assert llamadas[0][0] == ["git", "pull", "--ff-only", "--quiet"]
    assert llamadas[0][1]["cwd"] == repo


def test_pull_ff_only_devuelve_falso_si_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(
        instalador.subprocess,
        "run",
        lambda *args, **kwargs: _ResultadoFalso(returncode=1),
    )
    assert not instalador._pull_ff_only(str(tmp_path / "repo"))


# --- _copiar_bootstrap --------------------------------------------------------


def test_copiar_bootstrap_copia_a_destino_correcto(tmp_path):
    origen = tmp_path / "bootstrap" / "menu.py"
    origen.parent.mkdir()
    origen.write_text("print('bootstrap')\n", encoding="utf-8")
    destino = tmp_path / "nuke" / "menu.py"

    assert instalador._copiar_bootstrap(str(origen), str(destino))
    assert destino.read_text(encoding="utf-8") == "print('bootstrap')\n"


def test_copiar_bootstrap_sin_origen_devuelve_falso(tmp_path):
    destino = tmp_path / "menu.py"
    assert not instalador._copiar_bootstrap(str(tmp_path / "bootstrap" / "menu.py"), str(destino))
    assert not destino.exists()


# --- Guardias anti-fuga y pureza de import -----------------------------------


def test_instalador_sin_placeholder_tu_usuario():
    codigo = (_RAIZ / "instalar_script_editor.py").read_text(encoding="utf-8")
    assert "TU_USUARIO" not in codigo


def test_instalador_usa_url_real_del_repo_v2():
    codigo = (_RAIZ / "instalar_script_editor.py").read_text(encoding="utf-8")
    assert instalador.REPO_URL in codigo
    assert instalador.REPO_URL == "https://github.com/emanuelbarriga/saman-workflow-v2.git"


def test_bootstrap_sin_placeholder_tu_usuario():
    bootstrap = (_RAIZ / "bootstrap" / "menu.py").read_text(encoding="utf-8")
    assert "TU_USUARIO" not in bootstrap


def test_nuke_solo_se_importa_dentro_de_funciones():
    codigo = (_RAIZ / "instalar_script_editor.py").read_text(encoding="utf-8")
    violaciones = [
        linea
        for linea in codigo.splitlines()
        if re.match(r"^(import\s+nuke\b|from\s+nuke\b)", linea)
    ]
    assert violaciones == []


def test_import_headless_sin_nuke():
    # la suite corre en maquinas sin Nuke: importar la logica pura es la prueba
    assert instalador._estado_destino("no/existe") == "sin_checkout"