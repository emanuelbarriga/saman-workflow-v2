"""
Tests del bootstrap de artista V2 — slice H3 del cambio load-contract.

El bootstrap (``bootstrap/menu.py``) es el contrato de actualizacion V1
portado a V2: es SELF-CONTAINED (importa solo stdlib + ``nuke``, nunca
codigo del repo) y se instala en ``~/.nuke/menu.py``. Las 11 reglas V1 se
preservan; solo cambian los probes estructurales:

  - ``_checkout_completo`` probea ``SamanTools/core/rutas_engine.py`` (V2),
    ya no el modulo de registro de V1.
  - ``_cargar_menu_real`` ejecuta ``<checkout>/SamanTools/ui/menu.py``
    (target nuevo de H4; hasta que exista se tolera su ausencia).
  - auto-sync lee ``<checkout>/bootstrap/menu.py`` (mismo patron que V1).
  - Marcador de desinstalacion distinto: "SamanTools V2 bootstrap", para que
    el desinstalador de V1 no borre este bootstrap en coexistencia.

Estrategia de test (ADR-9): el fake de ``nuke`` vive en ``sys.modules``
(exclusivo de este archivo — conftest NO define stub y no se toca) y
``subprocess.run`` se monkeypatchea con un fake de git que registra los argv
fijos (nunca ``shell=True``) y responde por reglas. Las rutas de escenario son
siempre bajo ``tmp_path`` (ficticias).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fakes locales al test file (prohibido en conftest: el bootstrap es el unico
# consumidor de nuke y la suite debe correr sin Nuke instalado)
# ---------------------------------------------------------------------------


class _MenuFake:
    """Menu fake tipo Nuke: findItem/addMenu/addCommand con registro comun."""

    def __init__(self, registro, nombre=""):
        self.nombre = nombre
        self.items = {}
        self.registro = registro

    def findItem(self, nombre):
        return self.items.get(nombre)

    def addMenu(self, nombre):
        sub = _MenuFake(self.registro, nombre)
        self.items[nombre] = sub
        return sub

    def addCommand(self, nombre, fn=None):
        self.items[nombre] = fn
        self.registro.append(nombre)


class _NukeFake:
    """Modulo nuke fake: GUI/message/ask/menu con grabacion de llamadas."""

    def __init__(self, gui=True, ask=True):
        self.GUI = gui
        self._ask_result = ask
        self.messages = []
        self.asks = []
        self.menu_calls = []
        self.menu_registro = []
        self._menu = _MenuFake(self.menu_registro)

    def message(self, texto):
        self.messages.append(texto)

    def ask(self, texto):
        self.asks.append(texto)
        return self._ask_result

    def menu(self, nombre):
        self.menu_calls.append(nombre)
        return self._menu


class _GitFake:
    """Fake de ``subprocess.run`` para git: registra argv y responde por reglas.

    Cada regla es (patron, (rc, stdout, stderr), side_effect); el patron
    matchea elementos del argv completo. Los comandos se componen con argv
    fijo ``["git", "-C", TOOLS_DIR] + args`` (sin shell) — el fake verifica
    esa composicion real sin ejecutar git.
    """

    def __init__(self):
        self.calls = []
        self._reglas = []

    def agregar(self, patron, resultado=(0, b"", b""), side_effect=None):
        self._reglas.append((tuple(patron), resultado, side_effect))

    def __call__(self, argv, capture_output=True, timeout=60):
        self.calls.append(list(argv))
        for patron, (rc, out, err), efecto in self._reglas:
            if all(p in argv for p in patron):
                if efecto is not None:
                    efecto(argv)
                return subprocess.CompletedProcess(argv, rc, out, err)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def con(self, *tokens):
        return [c for c in self.calls if all(t in c for t in tokens)]

    def sin(self, *tokens):
        return not any(all(t in c for t in tokens) for c in self.calls)


def _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake):
    """Importa ``bootstrap/menu.py`` con TOOLS_DIR ficticio bajo tmp_path.

    El import ejecuta ``instalar()``: con un TOOLS_DIR vacio el arranque es
    silencioso (sin checkout -> sin clone, sin menu, sin alerta). Cada test
    reimporta un modulo fresco para aislar los falsos.
    """
    import importlib.util

    ruta = _RAIZ / "bootstrap" / "menu.py"
    monkeypatch.setitem(sys.modules, "nuke", nuke_fake)
    monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path / ".nuke" / "SamanTools"))
    spec = importlib.util.spec_from_file_location("saman_bootstrap_test", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _con_git(monkeypatch, mod):
    git = _GitFake()
    monkeypatch.setattr(mod.subprocess, "run", git)
    return git


# ---------------------------------------------------------------------------
# H3.1 — Regla 1: fetch-only al arranque (nunca pull/clone/reset)
# ---------------------------------------------------------------------------


def test_estado_update_ok_es_fetch_only(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["rev-parse", "HEAD"], (0, b"abc123\n", b""))
    git.agregar(["rev-parse", "origin/main"], (0, b"abc123\n", b""))

    assert mod._estado_update() == "ok"
    assert git.con("fetch", "origin", "main")
    assert git.sin("pull") and git.sin("clone") and git.sin("reset")


def test_estado_update_detecta_disponible(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    (Path(mod.TOOLS_DIR) / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["rev-parse", "HEAD"], (0, b"abc123\n", b""))
    git.agregar(["rev-parse", "origin/main"], (0, b"def456\n", b""))

    assert mod._estado_update() == "disponible"


def test_estado_update_fetch_fallido_devuelve_error(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    (Path(mod.TOOLS_DIR) / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (1, b"", b"sin red"))

    assert mod._estado_update() == "error"


def test_estado_update_sin_checkout_no_ejecuta_git(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)

    assert mod._estado_update() == "sin_checkout"
    assert git.calls == []


def test_estado_update_sin_git_no_intenta_nada(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    monkeypatch.setattr(mod, "_hay_git", lambda: False)

    assert mod._estado_update() == "sin_git"


# ---------------------------------------------------------------------------
# H3.1 — Reglas 2 y 3: consentimiento (alerta max 1/6h) + pull --ff-only
# ---------------------------------------------------------------------------


def test_aplicar_update_pull_ff_only_ok(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / "SamanTools").mkdir(parents=True)
    (tools / "SamanTools" / "__init__.py").write_text('__version__ = "2.0.0"\n')
    git = _con_git(monkeypatch, mod)
    git.agregar(["pull", "--ff-only", "--quiet"], (0, b"", b""))
    git.agregar(["rev-parse", "--short"], (0, b"abc123\n", b""))

    assert mod._aplicar_update() is True
    assert git.con("pull", "--ff-only")
    assert (tools / ".last_update").exists()
    assert any("actualizado correctamente" in m for m in nuke_fake.messages)


def test_aplicar_update_pull_fallido_mensaje_sin_reset(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    (Path(mod.TOOLS_DIR)).mkdir(parents=True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["pull", "--ff-only"], (1, b"", b"not fast-forward"))

    assert mod._aplicar_update() is False
    assert any("No se pudo actualizar" in m for m in nuke_fake.messages)
    assert "not fast-forward" in "\n".join(nuke_fake.messages)
    assert git.sin("reset") and git.sin("clone")


def test_alerta_automatica_rate_limit_6_horas(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    (tools / ".last_update").write_text("")  # mtime reciente: dentro de las 6 h
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)

    mod._alerta_automatica()
    assert nuke_fake.asks == []
    assert git.calls == []  # ni fetch: el rate-limit corta antes del chequeo


def test_alerta_automatica_sin_gui_no_hace_nada(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    (Path(mod.TOOLS_DIR) / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)

    mod._alerta_automatica()
    assert git.calls == []
    assert nuke_fake.asks == []


def test_alerta_automatica_declina_consentimiento_sin_pull(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True, ask=False)  # el artista dice que no
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["rev-parse", "HEAD"], (0, b"abc123\n", b""))
    git.agregar(["rev-parse", "origin/main"], (0, b"def456\n", b""))

    mod._alerta_automatica()
    assert len(nuke_fake.asks) == 1  # pidio consentimiento una sola vez
    assert git.sin("pull")           # declino: no se aplica nada
    assert (tools / ".last_update").exists()  # lock marcado pase lo que pase


# ---------------------------------------------------------------------------
# H3.1 — Regla 4: silencio sin checkout (nunca clona al boot, nunca error)
# ---------------------------------------------------------------------------


def test_cargar_menu_real_sin_checkout_silencio_total(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    git = _con_git(monkeypatch, mod)

    assert mod._cargar_menu_real() is False
    assert git.calls == []              # ni clone ni fetch ni reset
    assert nuke_fake.messages == []     # cero dialogos


# ---------------------------------------------------------------------------
# H3.1 — Regla 5: clone atomico via tmp + rename
# ---------------------------------------------------------------------------


def test_clonar_si_falta_tmp_rename_atomico(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)

    def crear_clone(argv):
        tmp = Path(argv[-1])
        (tmp / "SamanTools" / "core").mkdir(parents=True)
        (tmp / "SamanTools" / "core" / "rutas_engine.py").write_text("# probe\n")

    git = _con_git(monkeypatch, mod)
    git.agregar(["clone", "--depth", "1"], (0, b"", b""), side_effect=crear_clone)

    assert mod._clonar_si_falta() is True
    assert (tools / "SamanTools" / "core" / "rutas_engine.py").exists()
    residuos = [p for p in tools.parent.iterdir() if p.name.startswith(".saman_clone_tmp_")]
    assert residuos == []  # el tmp quedo renombrado, no colgado


def test_clonar_si_falta_fallo_limpia_tmp_y_deja_target_ausente(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)

    def crear_tmp_parcial(argv):
        Path(argv[-1]).mkdir(parents=True)  # git dejo un checkout a medias

    git = _con_git(monkeypatch, mod)
    git.agregar(["clone", "--depth", "1"], (1, b"", b"fatal: sin red"), side_effect=crear_tmp_parcial)

    assert mod._clonar_si_falta() is False
    assert not tools.exists()  # target intacto (ausente)
    residuos = [p for p in tools.parent.iterdir() if p.name.startswith(".saman_clone_tmp_")]
    assert residuos == []      # temporal eliminado


# ---------------------------------------------------------------------------
# H3.1 — Regla 6: reparacion silenciosa con reset --hard
# ---------------------------------------------------------------------------


def test_reparar_checkout_reset_hard_alinea_con_origin(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)

    def crear_probe(argv):
        (tools / "SamanTools" / "core").mkdir(parents=True, exist_ok=True)
        (tools / "SamanTools" / "core" / "rutas_engine.py").write_text("# probe\n")

    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["reset", "--hard", "origin/main"], (0, b"", b""), side_effect=crear_probe)

    assert mod._reparar_checkout() is True
    assert git.con("reset", "--hard", "origin/main")


# ---------------------------------------------------------------------------
# H3.2 — Probes V2: rutas_engine.py, exec ui/menu.py, sync bootstrap/menu.py
# ---------------------------------------------------------------------------


def test_checkout_completo_probea_rutas_engine(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    probe = tools / "SamanTools" / "core" / "rutas_engine.py"
    probe.parent.mkdir(parents=True)
    probe.write_text("")

    assert mod._checkout_completo() is True

    probe.unlink()
    assert mod._checkout_completo() is False


def test_cargar_menu_real_repara_y_ejecuta_ui_menu(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    (tools / "SamanTools" / "ui").mkdir(parents=True)
    # el target real (H4) importa nuke en su top-level (ADR-7): el fake lo imita
    (tools / "SamanTools" / "ui" / "menu.py").write_text(
        'import nuke\nnuke.message("menu real cargado OK")\n'
    )
    monkeypatch.setattr(mod, "_hay_git", lambda: True)

    def crear_probe(argv):
        (tools / "SamanTools" / "core").mkdir(parents=True, exist_ok=True)
        (tools / "SamanTools" / "core" / "rutas_engine.py").write_text("# probe\n")

    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["reset", "--hard", "origin/main"], (0, b"", b""), side_effect=crear_probe)

    assert mod._cargar_menu_real() is True
    assert git.con("reset", "--hard", "origin/main")
    assert any("menu real cargado OK" in m for m in nuke_fake.messages)


def test_cargar_menu_real_target_ausente_no_rompe(monkeypatch, tmp_path):
    """H4 crea el target; hasta entonces un checkout completo sin ui/menu.py
    debe devolver False sin dialogo ni reparacion (tolerancia al target)."""
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    (tools / "SamanTools" / "core").mkdir(parents=True)
    (tools / "SamanTools" / "core" / "rutas_engine.py").write_text("")
    git = _con_git(monkeypatch, mod)

    assert mod._cargar_menu_real() is False
    assert nuke_fake.messages == []
    assert git.calls == []  # checkout completo: ni reparacion ni clone


# ---------------------------------------------------------------------------
# H3.1 — Regla 7: auto-sync por hash del propio bootstrap
# ---------------------------------------------------------------------------


def test_auto_actualizar_bootstrap_sincroniza_por_md5(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    repo_boot = tools / "bootstrap" / "menu.py"
    repo_boot.parent.mkdir(parents=True)
    repo_boot.write_text("REPO_VERSION_NUEVA\n")
    instalado = tools.parent / "menu.py"  # ~/.nuke/menu.py instalado
    instalado.write_text("INSTALADO_VIEJO\n")
    monkeypatch.setattr(mod, "__file__", str(instalado))
    copias = []
    copy2_real = shutil.copy2  # capturar ANTES de parchear (evita recursion)

    def _copy2(src, dst):
        copias.append((src, dst))
        copy2_real(src, dst)

    monkeypatch.setattr(mod.shutil, "copy2", _copy2)

    mod._auto_actualizar_bootstrap()
    assert instalado.read_text() == "REPO_VERSION_NUEVA\n"
    assert len(copias) == 1


def test_auto_actualizar_bootstrap_no_copia_si_iguales(monkeypatch, tmp_path):
    mod = _cargar_bootstrap(tmp_path, monkeypatch, _NukeFake(gui=False))
    tools = Path(mod.TOOLS_DIR)
    repo_boot = tools / "bootstrap" / "menu.py"
    repo_boot.parent.mkdir(parents=True)
    repo_boot.write_text("MISMO\n")
    instalado = tools.parent / "menu.py"
    instalado.write_text("MISMO\n")
    monkeypatch.setattr(mod, "__file__", str(instalado))
    copias = []
    copy2_real = shutil.copy2

    def _copy2(src, dst):
        copias.append((src, dst))
        copy2_real(src, dst)

    monkeypatch.setattr(mod.shutil, "copy2", _copy2)

    mod._auto_actualizar_bootstrap()
    assert copias == []              # contenido identico: sin reescritura
    assert instalado.read_text() == "MISMO\n"


# ---------------------------------------------------------------------------
# H3.1 — Regla 8: menu de mantenimiento solo cuando hay checkout
# ---------------------------------------------------------------------------


def test_agregar_boton_menu_solo_con_checkout(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    (Path(mod.TOOLS_DIR) / ".git").mkdir(parents=True)

    mod._agregar_boton_menu()
    # V1: findItem + addMenu = dos consultas al menu raiz cuando falta
    assert nuke_fake.menu_calls == ["Nuke", "Nuke"]
    assert nuke_fake.menu_registro == [
        "Actualizar SamanTools...",
        "Desinstalar SamanTools...",
    ]


def test_agregar_boton_menu_sin_checkout_menu_limpio(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)

    mod._agregar_boton_menu()
    assert nuke_fake.menu_calls == []
    assert nuke_fake.menu_registro == []


# ---------------------------------------------------------------------------
# H3.1 — Regla 9: el boton Actualizar reinstala cuando falta el checkout
# ---------------------------------------------------------------------------


def test_actualizar_ahora_sin_checkout_reinstala(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True, ask=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)

    def crear_clone(argv):
        tmp = Path(argv[-1])
        (tmp / "SamanTools" / "core").mkdir(parents=True)
        (tmp / "SamanTools" / "core" / "rutas_engine.py").write_text("# probe\n")

    git = _con_git(monkeypatch, mod)
    git.agregar(["clone", "--depth", "1"], (0, b"", b""), side_effect=crear_clone)

    mod._actualizar_ahora()
    assert git.con("clone")
    assert (tools / "SamanTools" / "core" / "rutas_engine.py").exists()
    assert any("instalado correctamente" in m for m in nuke_fake.messages)


def test_actualizar_ahora_sin_checkout_consentimiento_negado(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True, ask=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)

    mod._actualizar_ahora()
    assert len(nuke_fake.asks) == 1
    assert git.sin("clone")
    assert nuke_fake.messages == []


def test_actualizar_ahora_con_checkout_al_dia(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    (tools / "SamanTools").mkdir(parents=True)
    (tools / "SamanTools" / "__init__.py").write_text('__version__ = "2.0.0"\n')
    monkeypatch.setattr(mod, "_hay_git", lambda: True)
    git = _con_git(monkeypatch, mod)
    git.agregar(["fetch"], (0, b"", b""))
    git.agregar(["rev-parse", "HEAD"], (0, b"abc123\n", b""))
    git.agregar(["rev-parse", "origin/main"], (0, b"abc123\n", b""))
    git.agregar(["rev-parse", "--short"], (0, b"abc123\n", b""))

    mod._actualizar_ahora()
    assert any("última versión" in m for m in nuke_fake.messages)
    assert "2.0.0" in "\n".join(nuke_fake.messages)


# ---------------------------------------------------------------------------
# H3.1 — Regla 10: uninstall definitivo (checkout + respaldos + bootstrap)
# ---------------------------------------------------------------------------


def test_desinstalar_ahora_borra_checkout_respaldos_y_bootstrap(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True, ask=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    (tools / "SamanTools" / "core").mkdir(parents=True)
    (tools / "SamanTools" / "core" / "rutas_engine.py").write_text("")
    respaldo = tools.parent / "SamanTools.desinstalado_20260101"
    respaldo.mkdir()
    boot = tools.parent / "menu.py"
    boot.write_text("# SamanTools V2 bootstrap\n")
    monkeypatch.setattr(mod, "__file__", str(boot))

    mod._desinstalar_ahora()
    assert not tools.exists()
    assert not respaldo.exists()
    assert not boot.exists()
    assert any("desinstalado" in m.lower() for m in nuke_fake.messages)


def test_desinstalar_ahora_no_toca_menu_ajeno(monkeypatch, tmp_path):
    nuke_fake = _NukeFake(gui=True, ask=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    boot = tools.parent / "menu.py"
    boot.write_text("mi propio menu de Nuke, sin marcador SamanTools\n")
    monkeypatch.setattr(mod, "__file__", str(boot))

    mod._desinstalar_ahora()
    assert boot.exists()  # archivo ajeno: no se borra
    assert any("no se tocó" in m.lower() for m in nuke_fake.messages)


def test_desinstalar_ahora_no_borra_bootstrap_v1(monkeypatch, tmp_path):
    """Coexistencia: un menu instalado por V1 (marcador V1) NO lo borra V2."""
    nuke_fake = _NukeFake(gui=True, ask=True)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    tools = Path(mod.TOOLS_DIR)
    (tools / ".git").mkdir(parents=True)
    boot = tools.parent / "menu.py"
    boot.write_text("# bootstrap de artista (menu V1)\n")
    monkeypatch.setattr(mod, "__file__", str(boot))

    mod._desinstalar_ahora()
    assert boot.exists()  # sin marcador V2: intacto


# ---------------------------------------------------------------------------
# H3.3 — Marcador distinto: "SamanTools V2 bootstrap", V1 immune
# ---------------------------------------------------------------------------


def test_marcador_v2_presente_y_v1_ausente_en_fuente():
    fuente = (_RAIZ / "bootstrap" / "menu.py").read_text(encoding="utf-8")
    assert "SamanTools V2 bootstrap" in fuente
    assert "bootstrap de artista" not in fuente  # el desinstalador V1 no lo reconoce


# ---------------------------------------------------------------------------
# H3.1 — Regla 11: self-contained (stdlib + nuke, nunca repo code)
# ---------------------------------------------------------------------------


def test_bootstrap_self_contained_no_importa_repo():
    fuente = (_RAIZ / "bootstrap" / "menu.py").read_text(encoding="utf-8")
    imports = [l for l in fuente.splitlines() if l.startswith(("import ", "from "))]
    assert imports  # debe importar algo (stdlib + nuke)
    assert all("SamanTools" not in l for l in imports)


def test_bootstrap_importa_headless_solo_con_nuke_fake(monkeypatch, tmp_path):
    """Carga sin Nuke real y sin repo code: solo stdlib + fake de nuke."""
    nuke_fake = _NukeFake(gui=False)
    mod = _cargar_bootstrap(tmp_path, monkeypatch, nuke_fake)
    assert mod.__name__ == "saman_bootstrap_test"
    assert mod._tiene_checkout() is False  # arranque silencioso sin checkout


# ---------------------------------------------------------------------------
# H3.2/H3.3 — Estructura de fuente: probes V2 y sync source
# ---------------------------------------------------------------------------


def test_probes_v2_estructura_de_fuente():
    fuente = (_RAIZ / "bootstrap" / "menu.py").read_text(encoding="utf-8")
    assert '"rutas_engine.py"' in fuente                  # probe de checkout V2
    assert "registro" not in fuente                       # probe V1 desplazado
    assert '"ui", "menu.py"' in fuente                    # exec target de H4
    assert '"bootstrap", "menu.py"' in fuente             # fuente de auto-sync
    assert mod_const_valido(fuente)


def mod_const_valido(fuente):
    # el marcador usado por el desinstalador debe ser el definido como constante
    return 'MARCADOR = "SamanTools V2 bootstrap"' in fuente