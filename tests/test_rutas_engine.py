"""Tests del motor de rutas V2: esquema 3x3 por usuario (cambio perfil-por-usuario, S1).

Este archivo cubre el motor ``SamanTools/core/rutas_engine.py`` con el nuevo
esquema D1/AD1 — ``{user: {TO_VFX|COMP|FROM_VFX: {macOS|Windows|Linux: root}}}``
— resolución SOLO por usuario (escalera hostname ELIMINADA, AD2), lock D6 y
onboarding D3 (TDD estricto):

* ``leer_perfiles`` — archivo inexistente → ``{}``; JSON malformado →
  ``ValueError``; devuelve el dict interno ``perfiles`` del envelope.
* ``guardar_perfiles`` — escritura atomica (tmp mismo directorio + ``os.replace``),
  conserva claves top-level desconocidas, merge POR ESPACIO (los tres espacios
  son independientes), entrada legacy reemplazada por la forma nueva (AD1),
  ``.saman/`` creado lazy BAJO lock (nunca en lectura).
* ``detectar_forma_perfil`` — ``"nuevo"`` si hay al menos un espacio 3x3;
  ``"legacy"`` si el perfil trae ``hosts``/``default`` sin espacios (AD1).
* ``crear_perfil_default`` — 3 espacios x 3 SO ficticios con slotting de la
  base inyectada por forma.
* ``ruta_para_espacio`` — root del espacio para el SO; ``None`` sin raise.
* ``_lock_perfiles`` — context manager sobre el archivo HERMANO
  ``path + ".lockdir"`` (directorio atomico, fiable en red; nunca el target:
  os.replace cambia el inode), reintentos
  3×2.0s → ``TimeoutError``; ``_lock_clase`` fcntl/msvcrt/no-op.
* Concurrencia REAL (G5/G6): dos procesos escriben usuarios distintos bajo
  lock; dos procesos onbordean el MISMO usuario y el perdedor devuelve el
  perfil del ganador sin duplicar.
* ``resolver_perfil(user, path)`` — ``perfiles.get(user)`` directo (sin
  hostname); desconocido o legacy → onboarding sin raise, nunca devuelve
  ``None``.
* ``asegurar_perfil(user, path, base=None)`` — onboarding bajo lock con
  re-read (carrera ganada → perfil del ganador sin reescribir).
* G7 — ``relativizar``/``absolutizar`` (D5 two-track) intactos.
* G7 — ``get_context`` (D4): ``{proyecto, plano, version, carpeta_salida,
  espacio, so, project_root}``; ``proyecto`` por corte estructural
  (``raiz_proyecto_desde_ruta``) con fallback al token del nombre;
  ``carpeta_salida`` SIEMPRE ``"[getenv PROJECT_ROOT]/COMP/"`` (AD3).
* G7 — ``variables_entorno(contexto, perfil=None)``: ``PROJECT_ROOT`` por
  corte (NUNCA base); PYTHON_* = raices del perfil para el SO actual; espacio
  faltante → fallback hermano ``reconstruir_rutas(dirname, basename)`` sin
  slash final; clave irresoluble OMITIDA, nunca ``""`` (AD7); nunca muta
  ``os.environ``.

Todas las rutas son ficticias (``/Volumes/estudio/2026/CINE/...``,
``L:/VFX/2026/CINE/...``, ``/mnt/estudio/2026/CINE/...``); ninguna ruta real
del estudio aparece en fixtures.
"""

import json
import multiprocessing
import os
import sys

import pytest

from SamanTools.core import rutas_engine


def _perfil_por_defecto():
    """Perfil 3x3 ficticio esperado de crear_perfil_default() (AD1/R1)."""
    return {
        "TO_VFX": {
            "macOS": "/Volumes/estudio/2026/CINE/TO_VFX",
            "Windows": "L:/VFX/2026/CINE/TO_VFX",
            "Linux": "/mnt/estudio/2026/CINE/TO_VFX",
        },
        "COMP": {
            "macOS": "/Volumes/estudio/2026/CINE/COMP",
            "Windows": "L:/VFX/2026/CINE/COMP",
            "Linux": "/mnt/estudio/2026/CINE/COMP",
        },
        "FROM_VFX": {
            "macOS": "/Volumes/estudio/2026/CINE/FROM_VFX",
            "Windows": "L:/VFX/2026/CINE/FROM_VFX",
            "Linux": "/mnt/estudio/2026/CINE/FROM_VFX",
        },
    }


def _perfil_legacy():
    """Forma VIEJA (hosts/default) que la resolucion debe regenerar (AD1)."""
    roots = _perfil_por_defecto()["COMP"]
    return {"hosts": {"ws1": roots}, "default": roots}


# --- Store: leer_perfiles -----------------------------------------------------


def test_leer_perfiles_archivo_inexistente_devuelve_vacio(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    assert rutas_engine.leer_perfiles(str(ruta)) == {}


def test_leer_perfiles_json_malformado_lanza_valueerror(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        rutas_engine.leer_perfiles(str(ruta))


def test_leer_perfiles_raiz_no_objeto_lanza_valueerror(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        rutas_engine.leer_perfiles(str(ruta))


def test_leer_perfiles_devuelve_dict_interno_del_envelope(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    envelope = {"perfiles": {"ana": _perfil_por_defecto()}}
    ruta.write_text(json.dumps(envelope), encoding="utf-8")
    assert rutas_engine.leer_perfiles(str(ruta)) == envelope["perfiles"]


def test_leer_perfiles_envelope_sin_clave_perfiles_devuelve_vacio(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text('{"version": 1}', encoding="utf-8")
    assert rutas_engine.leer_perfiles(str(ruta)) == {}


# --- Store: guardar_perfiles --------------------------------------------------


def test_guardar_perfiles_round_trip_sin_temporales(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    store = {"ana": _perfil_por_defecto()}
    rutas_engine.guardar_perfiles(ruta, store)
    assert rutas_engine.leer_perfiles(ruta) == store
    # El lockdir se crea y autolimpia en la escritura (D6-v2); sin temporales.
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json"]  # lockdir autolimpio (D6-v2)


def test_guardar_perfiles_preserva_claves_top_level_desconocidas(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_por_defecto()})
    with open(ruta, "r", encoding="utf-8") as f:
        envelope = json.load(f)
    envelope["version"] = 2
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(envelope, f)
    rutas_engine.guardar_perfiles(ruta, {"pedro": _perfil_por_defecto()})
    with open(ruta, "r", encoding="utf-8") as f:
        envelope_final = json.load(f)
    assert envelope_final["version"] == 2
    assert "ana" in envelope_final["perfiles"]
    assert "pedro" in envelope_final["perfiles"]


def test_guardar_perfiles_mergea_por_espacio_sin_borrar_otros(tmp_path):
    """Los tres espacios son INDEPENDIENTES (AD1): solo se toca el entrante."""
    ruta = str(tmp_path / "nuke_profiles.json")
    inicial = {"ana": _perfil_por_defecto(), "pedro": _perfil_por_defecto()}
    rutas_engine.guardar_perfiles(ruta, inicial)
    # Ana actualiza SOLO su COMP.macOS; TO_VFX/FROM_VFX/otros SO y pedro viven.
    nuevas_root = "/Volumes/estudio/2027/CINE/COMP"
    rutas_engine.guardar_perfiles(
        ruta, {"ana": {"COMP": {"macOS": nuevas_root}}}
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"]["COMP"]["macOS"] == nuevas_root
    assert store["ana"]["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert store["ana"]["TO_VFX"] == _perfil_por_defecto()["TO_VFX"]
    assert store["ana"]["FROM_VFX"] == _perfil_por_defecto()["FROM_VFX"]
    assert store["pedro"] == _perfil_por_defecto()


def test_guardar_perfiles_reemplaza_forma_legacy(tmp_path):
    """Escritura sobre entrada legacy: replace por la forma nueva (AD1)."""
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_legacy()})
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_por_defecto()})
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"] == _perfil_por_defecto()
    assert "hosts" not in store["ana"]
    assert "default" not in store["ana"]


def test_guardar_perfiles_perfil_no_objeto_lanza_valueerror(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    with pytest.raises(ValueError):
        rutas_engine.guardar_perfiles(ruta, {"ana": "no-es-dict"})


# --- detectar_forma_perfil (AD1) ----------------------------------------------


def test_detectar_forma_perfil_nuevo():
    assert rutas_engine.detectar_forma_perfil(_perfil_por_defecto()) == "nuevo"


def test_detectar_forma_perfil_parcial_con_un_espacio_es_nuevo():
    parcial = {"TO_VFX": {"macOS": "/Volumes/estudio/2026/CINE/TO_VFX"}}
    assert rutas_engine.detectar_forma_perfil(parcial) == "nuevo"


def test_detectar_forma_perfil_legacy_hosts_default():
    assert rutas_engine.detectar_forma_perfil(_perfil_legacy()) == "legacy"


def test_detectar_forma_perfil_sin_espacios_es_legacy():
    assert rutas_engine.detectar_forma_perfil({"default": {}}) == "legacy"


def test_detectar_forma_perfil_no_dict_o_vacio_es_legacy():
    assert rutas_engine.detectar_forma_perfil(None) == "legacy"
    assert rutas_engine.detectar_forma_perfil({}) == "legacy"
    assert rutas_engine.detectar_forma_perfil("ana") == "legacy"


# --- crear_perfil_default -----------------------------------------------------


def test_crear_perfil_default_sin_base_usa_3x3_ficticio():
    assert rutas_engine.crear_perfil_default(None) == _perfil_por_defecto()


def test_crear_perfil_default_slot_macos():
    perfil = rutas_engine.crear_perfil_default("/Volumes/estudio/2027")
    assert perfil["TO_VFX"]["macOS"] == "/Volumes/estudio/2027/TO_VFX"
    assert perfil["COMP"]["macOS"] == "/Volumes/estudio/2027/COMP"
    assert perfil["FROM_VFX"]["macOS"] == "/Volumes/estudio/2027/FROM_VFX"
    assert perfil["COMP"]["Windows"] == "L:/VFX/2026/CINE/COMP"
    assert perfil["COMP"]["Linux"] == "/mnt/estudio/2026/CINE/COMP"


def test_crear_perfil_default_slot_windows():
    perfil = rutas_engine.crear_perfil_default("L:/VFX/2027")
    assert perfil["TO_VFX"]["Windows"] == "L:/VFX/2027/TO_VFX"
    assert perfil["COMP"]["Windows"] == "L:/VFX/2027/COMP"
    assert perfil["FROM_VFX"]["Windows"] == "L:/VFX/2027/FROM_VFX"
    assert perfil["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE/COMP"


def test_crear_perfil_default_slot_linux():
    perfil = rutas_engine.crear_perfil_default("/mnt/estudio/2027")
    assert perfil["TO_VFX"]["Linux"] == "/mnt/estudio/2027/TO_VFX"
    assert perfil["COMP"]["Linux"] == "/mnt/estudio/2027/COMP"
    assert perfil["FROM_VFX"]["Linux"] == "/mnt/estudio/2027/FROM_VFX"
    assert perfil["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE/COMP"


def test_crear_perfil_default_forma_desconocida_conserva_3x3():
    assert rutas_engine.crear_perfil_default("/raro/otro/lugar") == _perfil_por_defecto()


# --- ruta_para_espacio (per-space tri-platform) -------------------------------


@pytest.mark.parametrize("espacio", ["TO_VFX", "COMP", "FROM_VFX"])
@pytest.mark.parametrize("so", ["macOS", "Windows", "Linux"])
def test_ruta_para_espacio_cada_combinacion(espacio, so):
    perfil = _perfil_por_defecto()
    assert rutas_engine.ruta_para_espacio(perfil, espacio, so) == perfil[espacio][so]


def test_ruta_para_espacio_combinacion_ausente_devuelve_none():
    perfil = {"COMP": {"macOS": "/Volumes/estudio/2026/CINE/COMP"}}
    assert rutas_engine.ruta_para_espacio(perfil, "COMP", "Linux") is None
    assert rutas_engine.ruta_para_espacio(perfil, "TO_VFX", "macOS") is None
    assert rutas_engine.ruta_para_espacio(None, "COMP", "macOS") is None


# --- Lock: _lock_clase factory (D6-v2: directorio atomico, fiable en red) -------


def test_lock_clase_siempre_devuelve_directorio_atomico():
    # Todas las plataformas usan _LockDir: es el unico fiable en storage
    # compartido (SMB/NFS/red) — fcntl/msvcrt se descartaron por el
    # TimeoutError real en produccion.
    for p in ("posix", "darwin", "linux", "nt", "windows", "plan9", ""):
        assert rutas_engine._lock_clase(p) is rutas_engine._LockDir


def test_lock_dir_adquiere_y_libera(tmp_path):
    """D6-v2: mkdir atomico -> somos duenos; liberar -> se puede re-adquirir."""
    lock = rutas_engine._LockDir(lock_dir=str(tmp_path / "perfiles.json.lockdir"))
    assert lock.intentar() is True
    assert os.path.isdir(str(tmp_path / "perfiles.json.lockdir"))
    lock.liberar()
    assert not os.path.exists(str(tmp_path / "perfiles.json.lockdir"))
    # re-adquisicion tras liberar
    assert lock.intentar() is True
    lock.liberar()


def test_lock_dir_segunda_instancia_no_adquiere_mientras_el_primero_tiene(tmp_path):
    """D6-v2: dos instancias contendiendo -> la 2da devuelve False hasta liberar."""
    dir_lock = str(tmp_path / "perfiles.lockdir")
    a = rutas_engine._LockDir(lock_dir=dir_lock)
    b = rutas_engine._LockDir(lock_dir=dir_lock)
    assert a.intentar() is True
    assert b.intentar() is False
    a.liberar()
    assert b.intentar() is True
    b.liberar()


def test_lock_dir_huerfano_se_reemplaza(tmp_path):
    """D6-v2: lock dejado por proceso muerto (pid inexistente) se reemplaza."""
    dir_lock = str(tmp_path / "perfiles.lockdir")
    os.makedirs(dir_lock, exist_ok=True)
    with open(os.path.join(dir_lock, "pid"), "w", encoding="utf-8") as f:
        f.write("999999")  # pid gigante que no existe
    lock = rutas_engine._LockDir(lock_dir=dir_lock)
    assert lock.intentar() is True  # reemplaza el huerfano
    lock.liberar()


# --- Lock: _lock_perfiles context manager --------------------------------------


def test_lock_perfiles_usa_sibling_y_libera_al_salir(monkeypatch, tmp_path):
    instancias = []

    class LockFalsoRastreador:
        def __init__(self, lock_dir=None, fd=None):
            self.lock_dir = lock_dir
            self.liberado = False
            instancias.append(self)

        def intentar(self):
            return True

        def liberar(self):
            self.liberado = True

    monkeypatch.setattr(rutas_engine, "_lock_clase", lambda plataforma: LockFalsoRastreador)
    ruta = str(tmp_path / "perfiles.json")
    with rutas_engine._lock_perfiles(ruta):
        assert len(instancias) == 1
        assert instancias[0].lock_dir == ruta + ".lockdir"
        assert instancias[0].liberado is False
    assert instancias[0].liberado is True
    # el lockdir se limpia al liberar (no queda archivo/dir residual)
    assert not os.path.exists(ruta + ".lockdir")


def test_lock_perfiles_agotado_lanza_timeouterror(monkeypatch, tmp_path):
    class LockAtascado:
        def __init__(self, lock_dir=None, fd=None):
            pass

        def intentar(self):
            return False  # lock externo nunca se libera: simulacion de agotamiento

        def liberar(self):
            pass

    monkeypatch.setattr(rutas_engine, "_lock_clase", lambda plataforma: LockAtascado)
    monkeypatch.setattr(rutas_engine, "_PLAZO_INTENTO_S", 0.01)
    monkeypatch.setattr(rutas_engine.time, "sleep", lambda s: None)
    with pytest.raises(TimeoutError, match="No se pudo adquirir lock de perfiles"):
        with rutas_engine._lock_perfiles(str(tmp_path / "perfiles.json")):
            pass  # nunca se debe llegar aqui: el lock esta agotado


# --- .saman/ lazy bajo lock, nunca en lectura (task 1.3) ----------------------


def test_guardar_perfiles_crea_directorio_padre_lazy(tmp_path):
    """`.saman/` se crea EN LA PRIMERA ESCRITURA (bajo lock), no antes."""
    ruta = tmp_path / "estudio" / "CINE" / ".saman" / "nuke_profiles.json"
    rutas_engine.guardar_perfiles(str(ruta), {"ana": _perfil_por_defecto()})
    assert ruta.parent.is_dir()
    assert rutas_engine.leer_perfiles(str(ruta)) == {"ana": _perfil_por_defecto()}


def test_lectura_nunca_crea_directorio_padre(tmp_path):
    """Readers no lockean y NUNCA crean `.saman/` (AD6): store ausente -> {}."""
    ruta = tmp_path / "estudio" / "CINE" / ".saman" / "nuke_profiles.json"
    assert rutas_engine.leer_perfiles(str(ruta)) == {}
    assert not ruta.parent.exists()


# --- Concurrencia REAL (harness de runtime, D8) --------------------------------


def _worker_guardar_perfiles(ruta, usuario, bar):
    """Worker de proceso: espera la barrera y guarda SU perfil 3x3 bajo lock."""
    bar.wait()
    rutas_engine.guardar_perfiles(ruta, {usuario: rutas_engine.crear_perfil_default()})


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="el lock fcntl POSIX (requisito de este test) no existe en Windows",
)
def test_guardar_concurrente_multiproceso_no_pierde_perfiles(tmp_path):
    """Dos procesos escriben usuarios distintos con barrera; ambos sobreviven."""
    ruta = str(tmp_path / "nuke_profiles.json")
    ctx = multiprocessing.get_context()
    bar = ctx.Barrier(2)
    p1 = ctx.Process(target=_worker_guardar_perfiles, args=(ruta, "ana", bar))
    p2 = ctx.Process(target=_worker_guardar_perfiles, args=(ruta, "pedro", bar))
    p1.start()
    p2.start()
    p1.join(45)
    p2.join(45)
    assert p1.exitcode == 0, f"worker ana fallo (exitcode {p1.exitcode})"
    assert p2.exitcode == 0, f"worker pedro fallo (exitcode {p2.exitcode})"
    store = rutas_engine.leer_perfiles(ruta)
    esperado = rutas_engine.crear_perfil_default()
    assert store["ana"] == esperado
    assert store["pedro"] == esperado
    # Sin temporales: lockdir autolimpio (D6-v2); solo queda el store.
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json"]  # lockdir autolimpio (D6-v2)


def _worker_resolver_perfil(ruta, usuario, bar, cola):
    """Worker de proceso: espera la barrera y resuelve (onbordea si hace falta)."""
    try:
        bar.wait()
        cola.put(rutas_engine.resolver_perfil(usuario, ruta))
    except Exception as exc:  # pragma: no cover - el padre falla con el objeto
        cola.put(exc)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="el lock fcntl POSIX (requisito de este test) no existe en Windows",
)
def test_onboarding_concurrente_mismo_usuario_no_duplica(tmp_path):
    """Dos procesos onbordean el MISMO usuario sobre store vacio con barrera.

    El perdedor de la carrera read→lock→write relee bajo lock, encuentra el
    perfil del ganador y lo devuelve: el store final tiene EXACTAMENTE un
    ``nuevo`` (sin duplicados ni pisados) y sin temporales.
    """
    ruta = str(tmp_path / "nuke_profiles.json")
    ctx = multiprocessing.get_context()
    bar = ctx.Barrier(2)
    cola = ctx.Queue()
    p1 = ctx.Process(target=_worker_resolver_perfil, args=(ruta, "nuevo", bar, cola))
    p2 = ctx.Process(target=_worker_resolver_perfil, args=(ruta, "nuevo", bar, cola))
    p1.start()
    p2.start()
    p1.join(45)
    p2.join(45)
    assert p1.exitcode == 0, f"worker 1 fallo (exitcode {p1.exitcode})"
    assert p2.exitcode == 0, f"worker 2 fallo (exitcode {p2.exitcode})"
    r1 = cola.get(timeout=10)
    r2 = cola.get(timeout=10)
    assert isinstance(r1, dict) and isinstance(r2, dict), f"worker devolvio excepcion: {r1!r} {r2!r}"
    esperado = rutas_engine.crear_perfil_default()
    assert r1 == r2 == esperado
    store = rutas_engine.leer_perfiles(ruta)
    assert store == {"nuevo": esperado}
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json"]  # lockdir autolimpio (D6-v2)


# --- resolver_perfil (spec: resolution by user, sin hostname) -----------------


def test_resolver_perfil_usuario_conocido_devuelve_3x3(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_por_defecto()})
    assert rutas_engine.resolver_perfil("ana", ruta) == _perfil_por_defecto()


def test_resolver_perfil_desconocido_onboarding_persiste_y_segundo_resolve(tmp_path):
    """Spec: store sin 'nuevo' y path escribible → onboarding sin raise."""
    ruta = str(tmp_path / "nuke_profiles.json")
    perfil = rutas_engine.resolver_perfil("nuevo", ruta)
    assert perfil == _perfil_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"] == _perfil_por_defecto()
    # espec: "a later resolver_perfil for that user MUST return it"
    assert rutas_engine.resolver_perfil("nuevo", ruta) == _perfil_por_defecto()


def test_resolver_perfil_legacy_se_regenera_con_forma_nueva(tmp_path):
    """Legacy detectado en resolucion → re-onboarding con la forma nueva."""
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_legacy()})
    perfil = rutas_engine.resolver_perfil("ana", ruta)
    assert perfil == _perfil_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store["ana"] == _perfil_por_defecto()
    assert "hosts" not in store["ana"]


def test_resolver_perfil_determinismo_mismos_inputs_mismos_outputs(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_por_defecto()})
    r1 = rutas_engine.resolver_perfil("ana", ruta)
    r2 = rutas_engine.resolver_perfil("ana", ruta)
    assert r1 == r2 == _perfil_por_defecto()


# --- asegurar_perfil (onboarding bajo lock, D3) -------------------------------


def test_asegurar_perfil_crea_y_devuelve_3x3(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    perfil = rutas_engine.asegurar_perfil("lucia", ruta)
    assert perfil == _perfil_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store["lucia"] == _perfil_por_defecto()


def test_asegurar_perfil_base_inyectada_rellena_slot_linux(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    perfil = rutas_engine.asegurar_perfil("rafa", ruta, base="/mnt/estudio/2027")
    assert perfil["COMP"]["Linux"] == "/mnt/estudio/2027/COMP"
    assert perfil["TO_VFX"]["Linux"] == "/mnt/estudio/2027/TO_VFX"
    assert perfil["COMP"]["macOS"] == "/Volumes/estudio/2026/CINE/COMP"


def test_asegurar_perfil_carrera_ganada_devuelve_existente_sin_reescribir(tmp_path):
    """Carrera simulada: el otro proceso ya creo el perfil entre lectura y lock.

    El re-read bajo lock encuentra el perfil nuevo del ganador y lo devuelve
    SIN reescribir: nada de roots ficticias por encima ni claves ajenas.
    """
    custom = {
        "COMP": {"macOS": "/Volumes/custom/2026/CINE/COMP"},
        "TO_VFX": {"macOS": "/Volumes/custom/2026/CINE/TO_VFX"},
        "FROM_VFX": {"macOS": "/Volumes/custom/2026/CINE/FROM_VFX"},
    }
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"nuevo": custom})
    perfil = rutas_engine.asegurar_perfil("nuevo", ruta)
    assert perfil == custom  # el ganador, no el default ficticio
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"] == custom  # sin rewrite: nada ajeno se agrego


def test_asegurar_perfil_legacy_regenera_flagged(tmp_path):
    """AD1: escritura sobre legacy regenera la forma nueva (flag via forma)."""
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": _perfil_legacy()})
    perfil = rutas_engine.asegurar_perfil("ana", ruta)
    assert perfil == _perfil_por_defecto()
    assert rutas_engine.detectar_forma_perfil(perfil) == "nuevo"


# --- G7: Relativizacion / absolutizacion (D5 two-track) -----------------------


def test_relativizar_macos_absoluto_a_placeholder():
    """Spec: ruta bajo la base → '[getenv PROJECT_ROOT]/<rel>'."""
    ruta = "/Volumes/estudio/2026/CINE/TO_VFX/ep.nk"
    assert rutas_engine.relativizar(ruta, "/Volumes/estudio/2026") == "[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk"


def test_relativizar_fuera_de_base_intacto():
    """Spec: ruta fuera de la base → sin cambios."""
    assert rutas_engine.relativizar("/elsewhere/x.nk", "/Volumes/estudio/2026") == "/elsewhere/x.nk"


def test_relativizar_windows_casing_y_separador_preserva_casing():
    """D8: variante Windows case/separator relativiza Y conserva 'CINE/TO_VFX'."""
    result = rutas_engine.relativizar(r"l:\vfx\2026\CINE\TO_VFX\ep.nk", "L:/VFX/2026")
    assert result == "[getenv PROJECT_ROOT]/CINE/TO_VFX/ep.nk"


def test_relativizar_drive_minuscula_equivale_drive_mayuscula():
    """Spec: 'l:/vfx/2026' ≡ 'L:/VFX/2026' (equivalencia drive case-insensitive)."""
    assert rutas_engine.relativizar("L:/VFX/2026/CINE/ep.nk", "l:/vfx/2026") == "[getenv PROJECT_ROOT]/CINE/ep.nk"


def test_relativizar_prefijo_parcial_estudio2026_rechazado():
    """D5: guard de prefijo parcial — '/Volumes/estudio2026/...' NO cae bajo la base."""
    assert rutas_engine.relativizar("/Volumes/estudio2026/CINE/x.nk", "/Volumes/estudio/2026") == "/Volumes/estudio2026/CINE/x.nk"


def test_absolutizar_placeholder_a_macos_absoluto():
    """Spec: '[getenv PROJECT_ROOT]' se expande a la base inyectada."""
    assert rutas_engine.absolutizar("[getenv PROJECT_ROOT]/CINE/ep.nk", "/Volumes/estudio/2026") == "/Volumes/estudio/2026/CINE/ep.nk"


def test_absolutizar_windows_round_trip_forward_slashes():
    """Spec: round-trip Windows — slashes forward, drive case-insensitive."""
    assert rutas_engine.absolutizar("[getenv PROJECT_ROOT]/CINE/ep.nk", "L:/VFX/2026") == "L:/VFX/2026/CINE/ep.nk"


def test_absolutizar_base_inyectada_verbatim():
    """D5: absolutizar sustituye la base inyectada VERBATIM (casing original)."""
    assert rutas_engine.absolutizar("[getenv PROJECT_ROOT]/CINE/ep.nk", "l:/vfx/2026") == "l:/vfx/2026/CINE/ep.nk"


def test_relativizar_absolutizar_round_trip_macos():
    """Round-trip: relativizar → absolutizar reconstruye la ruta absoluta."""
    original = "/Volumes/estudio/2026/CINE/TO_VFX/ep.nk"
    rel = rutas_engine.relativizar(original, "/Volumes/estudio/2026")
    assert rel.startswith("[getenv PROJECT_ROOT]/")
    assert rutas_engine.absolutizar(rel, "/Volumes/estudio/2026") == original


def test_normalizar_para_comparar_canonico():
    """D5: copia canonica — backslashes→slashes, strip, rstrip '/', lower() total."""
    assert rutas_engine._normalizar_para_comparar("L:\\VFX\\2026\\") == "l:/vfx/2026"
    assert rutas_engine._normalizar_para_comparar("  /Volumes/estudio/2026/  ") == "/volumes/estudio/2026"


# --- G7: get_context (API de contexto, D4) --------------------------------------


def test_plato_basename_contexto_con_espacio_y_so_none():
    """Plato SOLO con basename: no hay raiz de espacio ni corte; proyecto del nombre."""
    ctx = rutas_engine.get_context(_perfil_por_defecto(), "CINE_107_008_00100_V01.mov")
    assert ctx["proyecto"] == "CINE"
    assert ctx["plano"] == "008_00100"
    assert ctx["version"] == "V01"
    assert ctx["espacio"] is None
    assert ctx["so"] is None
    assert ctx["project_root"] is None
    assert set(ctx.keys()) == {"proyecto", "plano", "version", "carpeta_salida", "espacio", "so", "project_root"}


def test_contexto_desde_raiz_de_espacio_comp():
    """Spec: plato bajo la raiz COMP → proyecto por corte y carpeta_salida token."""
    ctx = rutas_engine.get_context(
        _perfil_por_defecto(),
        "/Volumes/estudio/2026/CINE/COMP/EP_100/CINE_107_008_00100_V01.mov",
    )
    assert ctx["proyecto"] == "CINE"
    assert ctx["plano"] == "008_00100"
    assert ctx["version"] == "V01"
    assert ctx["carpeta_salida"] == "[getenv PROJECT_ROOT]/COMP/"
    assert ctx["espacio"] == "COMP"
    assert ctx["so"] == "macOS"
    assert ctx["project_root"] == "/Volumes/estudio/2026/CINE"


def test_contexto_desde_raiz_to_vfx_mac():
    """Plato bajo la raiz TO_VFX macOS → espacio='TO_VFX', so='macOS'."""
    ctx = rutas_engine.get_context(
        _perfil_por_defecto(),
        "/Volumes/estudio/2026/CINE/TO_VFX/EP_107/CINE_107_008_00100_V01.mov",
    )
    assert ctx["espacio"] == "TO_VFX"
    assert ctx["so"] == "macOS"
    assert ctx["project_root"] == "/Volumes/estudio/2026/CINE"


def test_contexto_windows_plato_deriva_espacio_y_so():
    """Plato Windows (backslashes) bajo la raiz L:/VFX/2026/CINE/TO_VFX."""
    ctx = rutas_engine.get_context(
        _perfil_por_defecto(),
        r"L:\VFX\2026\CINE\TO_VFX\EP_107\CINE_107_008_00100_V01.mov",
    )
    assert ctx["proyecto"] == "CINE"
    assert ctx["espacio"] == "TO_VFX"
    assert ctx["so"] == "Windows"
    assert ctx["project_root"] == "L:/VFX/2026/CINE"


def test_contexto_determinismo_inputs_identicos():
    """Spec: inputs identicos → dicts identicos (misma llamada dos veces)."""
    perfil = _perfil_por_defecto()
    plato = "/Volumes/estudio/2026/CINE/COMP/EP_100/CINE_107_008_00100_V01.mov"
    assert rutas_engine.get_context(perfil, plato) == rutas_engine.get_context(perfil, plato)


def test_contexto_version_malformada_no_lanza():
    """Nombre con version en el medio: sin raise, version movida al final (nombres)."""
    ctx = rutas_engine.get_context(_perfil_por_defecto(), "CINE_108_012_V01_0100.mov")
    assert ctx["proyecto"] == "CINE"
    assert ctx["plano"] == "012_0100"
    assert ctx["version"] == "V01"


def test_contexto_carpeta_salida_siempre_token_comp():
    """AD3: carpeta_salida = '[getenv PROJECT_ROOT]/COMP/' (sin segmento proyecto)."""
    ctx = rutas_engine.get_context(
        _perfil_por_defecto(),
        "/Volumes/estudio/2026/CINE/FROM_VFX/EP_107/CINE_107_008_00100_V01.mov",
    )
    assert ctx["carpeta_salida"] == "[getenv PROJECT_ROOT]/COMP/"


# --- G7: variables_entorno (contrato TCL, AD7) ---------------------------------


def test_env_contracto_corte_project_root_y_raices_del_perfil():
    """Spec: PROJECT_ROOT por corte estructural + PYTHON_* desde el perfil."""
    perfil = _perfil_por_defecto()
    ctx = rutas_engine.get_context(
        perfil, "/Volumes/estudio/2026/CINE/COMP/EP_107/CINE_107_008_00100_V01.mov"
    )
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert env["PYTHON_TO_VFX"] == "/Volumes/estudio/2026/CINE/TO_VFX"
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"
    assert env["PYTHON_FROM_VFX"] == "/Volumes/estudio/2026/CINE/FROM_VFX"
    # Raices del perfil: SIN slash final (contrato nuevo, distinto de V1).
    assert not env["PYTHON_COMP"].endswith("/")


def test_env_sin_perfil_fallback_hermano_reconstruir_rutas():
    """AD7: sin perfil, PYTHON_* caen al hermano reconstruir_rutas(dirname,basename)."""
    ctx = rutas_engine.get_context(
        _perfil_por_defecto(), "/Volumes/estudio/2026/CINE/TO_VFX/EP_107/CINE_107_008_00100_V01.mov"
    )
    env = rutas_engine.variables_entorno(ctx)  # perfil=None: todo via fallback
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"


def test_env_espacio_faltante_usa_sibling_y_el_presente_usa_perfil():
    """Espacio ausente en el perfil → reconstruir_rutas; el presente → perfil."""
    perfil = {
        "TO_VFX": {"macOS": "/Volumes/otro/2026/CINE/TO_VFX"},
        "FROM_VFX": {"macOS": "/Volumes/estudio/2026/CINE/FROM_VFX"},
        # COMP ausente en macOS: debe caer al fallback hermano del corte
    }
    ctx = rutas_engine.get_context(
        perfil, "/Volumes/otro/2026/CINE/TO_VFX/EP_107/CINE_107_008_00100_V01.mov"
    )
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert env["PYTHON_TO_VFX"] == "/Volumes/otro/2026/CINE/TO_VFX"  # del perfil
    assert env["PYTHON_COMP"] == "/Volumes/otro/2026/CINE/COMP"  # hermano (corte)
    # FROM_VFX del perfil se conserva tal cual
    assert env["PYTHON_FROM_VFX"] == "/Volumes/estudio/2026/CINE/FROM_VFX"


def test_env_clave_irresoluble_se_omite_nunca_vacia():
    """AD7: SO no soportado → PYTHON_* OMITIDAS (nunca ""), PROJECT_ROOT queda."""
    env = rutas_engine.variables_entorno(
        {"project_root": "/mnt/estudio/2026/CINE", "so": "Solaris"}
    )
    assert env == {"PROJECT_ROOT": "/mnt/estudio/2026/CINE"}
    assert "" not in env.values()


def test_env_sin_datos_devuelve_vacio():
    assert rutas_engine.variables_entorno({"proyecto": "CINE"}) == {}
    assert rutas_engine.variables_entorno(None) == {}
    assert rutas_engine.variables_entorno("x") == {}


def test_env_no_muta_os_environ():
    """Spec: contrato PURO — os.environ queda intacto tras la llamada."""
    antes = dict(os.environ)
    perfil = _perfil_por_defecto()
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert dict(os.environ) == antes


# --- espacios-extra: sanitizador de clave de entorno (R2/R8) ------------------


def test_clave_env_para_espacio_3d_y_matte_paint():
    """spec: '3D'→'3D', 'matte paint'→'MATTE_PAINT' (sufijos estables)."""
    assert rutas_engine._clave_env_para_espacio("3D") == "3D"
    assert rutas_engine._clave_env_para_espacio("matte paint") == "MATTE_PAINT"


def test_clave_env_para_espacio_colapsa_guiones_y_recorta_extremos():
    """spec: colapsa corridas de '_' y hace strip('_') en los extremos."""
    assert rutas_engine._clave_env_para_espacio("  doble  espacio ") == "DOBLE_ESPACIO"
    assert rutas_engine._clave_env_para_espacio("pre--post") == "PRE_POST"


def test_clave_env_para_espacio_compone_clave_python():
    """spec: la clave de entorno es SIEMPRE 'PYTHON_' + sufijo sanitizado."""
    assert "PYTHON_" + rutas_engine._clave_env_para_espacio("3D") == "PYTHON_3D"
    assert "PYTHON_" + rutas_engine._clave_env_para_espacio("matte paint") == "PYTHON_MATTE_PAINT"


@pytest.mark.parametrize(
    "nombre",
    [
        "foo/bar",   # R8: forma de ruta
        "{}",        # R8: JSON-reserved-looking
        "---",       # sanitiza a vacio
        "",          # vacio
        "   ",       # solo espacios: sanitiza a vacio
        "HOSTS",     # R2: legacy
        "DEFAULT",   # R2: legacy
    ],
)
def test_clave_env_para_espacio_rechaza_nombres_invalidos(nombre):
    """spec/R8/R2: nombres invalidos → ValueError, nunca producen clave."""
    with pytest.raises(ValueError):
        rutas_engine._clave_env_para_espacio(nombre)


# --- espacios-extra: variables_entorno con extras (D3/D4/R6) ------------------


def _perfil_con_extras():
    """Perfil 3x3 + dos extras; insercion NO ordenada para probar sorted()."""
    perfil = _perfil_por_defecto()
    perfil["matte paint"] = {"macOS": "/Volumes/estudio/2026/CINE/matte_paint"}
    perfil["3D"] = {"macOS": "/Volumes/estudio/2026/CINE/3D"}
    return perfil


def test_env_extras_orden_canonico_primero_y_sorted():
    """spec: canonicos en orden _ESPACIOS, luego extras ordenados (sorted)."""
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    env = rutas_engine.variables_entorno(ctx, perfil=_perfil_con_extras())
    claves = list(env.keys())
    assert claves[:4] == [
        "PROJECT_ROOT",
        "PYTHON_TO_VFX",
        "PYTHON_COMP",
        "PYTHON_FROM_VFX",
    ]
    # "3D" < "matte paint" lexicograficamente, aunque se insertaron al reves
    assert claves[4:] == ["PYTHON_3D", "PYTHON_MATTE_PAINT"]
    assert env["PYTHON_3D"] == "/Volumes/estudio/2026/CINE/3D"
    assert env["PYTHON_MATTE_PAINT"] == "/Volumes/estudio/2026/CINE/matte_paint"


def test_env_extras_determinismo_mismos_inputs_mismo_dict():
    """spec: inputs identicos → dict identico (orden canonico + sorted extras)."""
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    a = rutas_engine.variables_entorno(ctx, perfil=_perfil_con_extras())
    b = rutas_engine.variables_entorno(ctx, perfil=_perfil_con_extras())
    # No basta con a == b: ambos deben CONTENER los extras (RED real).
    esperado = {
        "PROJECT_ROOT": "/Volumes/estudio/2026/CINE",
        "PYTHON_TO_VFX": "/Volumes/estudio/2026/CINE/TO_VFX",
        "PYTHON_COMP": "/Volumes/estudio/2026/CINE/COMP",
        "PYTHON_FROM_VFX": "/Volumes/estudio/2026/CINE/FROM_VFX",
        "PYTHON_3D": "/Volumes/estudio/2026/CINE/3D",
        "PYTHON_MATTE_PAINT": "/Volumes/estudio/2026/CINE/matte_paint",
    }
    assert a == b == esperado


def test_env_extra_sin_root_para_so_se_omite():
    """spec: extra sin root para el SO actual → clave AUSENTE, nunca ``""``."""
    perfil = _perfil_por_defecto()
    perfil["3D"] = {"Windows": "L:/VFX/2026/CINE/3D"}  # sin root macOS
    perfil["PREVIEW"] = {"macOS": "/Volumes/estudio/2026/CINE/PREVIEW"}  # presente
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert "PYTHON_3D" not in env
    assert env["PYTHON_PREVIEW"] == "/Volumes/estudio/2026/CINE/PREVIEW"
    assert "" not in env.values()
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"


def test_env_extra_insanitizable_se_omite_y_no_lanza():
    """D4: clave de store sucia (foo/bar) → omitida, nunca raise, nunca ``""``."""
    perfil = _perfil_por_defecto()
    perfil["foo/bar"] = {"macOS": "/Volumes/estudio/2026/CINE/foo"}
    perfil["PREVIEW"] = {"macOS": "/Volumes/estudio/2026/CINE/PREVIEW"}
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert "PYTHON_FOO_BAR" not in env
    assert "" not in env.values()
    # los canonicos y los extras validos siguen emitiendose: la omision no rompe el loop
    assert env["PYTHON_COMP"] == "/Volumes/estudio/2026/CINE/COMP"
    assert env["PYTHON_PREVIEW"] == "/Volumes/estudio/2026/CINE/PREVIEW"


def test_env_extra_presente_y_canonico_faltante_fallback_hermano_intacto():
    """R6/D3: el extra usa su root; el canonico faltante cae al hermano."""
    perfil = {
        "TO_VFX": {"macOS": "/Volumes/otro/2026/CINE/TO_VFX"},
        "FROM_VFX": {"macOS": "/Volumes/estudio/2026/CINE/FROM_VFX"},
        "3D": {"macOS": "/Volumes/estudio/2026/CINE/3D"},
        # COMP ausente en macOS → fallback hermano del corte
    }
    ctx = {"project_root": "/Volumes/otro/2026/CINE", "so": "macOS"}
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert env["PYTHON_COMP"] == "/Volumes/otro/2026/CINE/COMP"  # hermano (corte)
    assert env["PYTHON_3D"] == "/Volumes/estudio/2026/CINE/3D"  # del perfil


def test_env_extra_no_es_marcador_de_corte_estructural():
    """R6: un extra NUNCA corta el proyecto; su root si se emite como env."""
    plato = "/Volumes/estudio/2026/CINE/3D/ep.nk"
    assert rutas_engine.raiz_proyecto_desde_ruta(plato) is None  # sin corte en '3D'
    perfil = _perfil_por_defecto()
    perfil["3D"] = {"macOS": "/Volumes/estudio/2026/CINE/3D"}
    ctx = {"project_root": "/Volumes/estudio/2026/CINE", "so": "macOS"}
    env = rutas_engine.variables_entorno(ctx, perfil=perfil)
    assert env["PROJECT_ROOT"] == "/Volumes/estudio/2026/CINE"
    assert env["PYTHON_3D"] == "/Volumes/estudio/2026/CINE/3D"