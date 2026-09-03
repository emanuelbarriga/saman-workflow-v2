"""Tests del motor de rutas: store + lock (G5) y resolucion + onboarding (G6).

Este archivo cubre el motor ``SamanTools/core/rutas_engine.py`` (esquema D1,
lock D6, precedencia D2, onboarding D3, TDD estricto):

* ``leer_perfiles`` — archivo inexistente → ``{}``; JSON malformado → ``ValueError``;
  devuelve el dict interno ``perfiles`` del envelope.
* ``guardar_perfiles`` — escritura atomica (tmp mismo directorio + ``os.replace``),
  conserva claves top-level desconocidas, merge por usuario (nunca replace a ciegas).
* ``crear_perfil_default`` — roots ficticias por plataforma con slotting por forma
  de la base inyectada.
* ``_lock_perfiles`` — context manager sobre el archivo HERMANO ``path + ".lock"``
  (nunca el target: os.replace cambia el inode), reintentos 3×2.0s → ``TimeoutError``.
* ``_lock_clase`` — factory fcntl/msvcrt/no-op con plataforma inyectada.
* Concurrencia REAL (G5): dos procesos escriben perfiles distintos bajo lock con
  barrera de arranque en POSIX; el resultado final contiene AMBOS perfiles.
* ``_emparejar_perfil`` — escalera de precedencia D2: par exacto → user-only
  default → hostname-only (primer usuario en orden de documento) → ``None``
  (marcador de onboarding; la API publica lo absorbe).
* ``resolver_perfil`` — par conocido y fallback user-only; desconocido →
  onboarding sin raise; determinismo (mismos inputs → mismos outputs).
* ``asegurar_perfil`` — onboarding bajo lock: re-read + re-resolve (carrera
  ganada devuelve el ganador sin reescribir), merge por usuario, base inyectada
  con slotting.
* ``ruta_para_plataforma`` — raiz por plataforma; ``None`` si la plataforma
  no esta en el perfil.
* Concurrencia REAL (G6): dos procesos onbordean el MISMO par sobre store vacio;
  el perdedor devuelve el perfil del ganador y no duplica.

Todas las rutas son ficticias (``/Volumes/estudio/2026``, ``L:/VFX/2026``,
``/mnt/estudio/2026``); ninguna ruta real del estudio aparece en fixtures.
"""

import json
import multiprocessing
import os
import sys

import pytest

from SamanTools.core import rutas_engine


def _roots_por_defecto():
    """Roots ficticias por plataforma esperadas de crear_perfil_default()."""
    return {"macOS": "/Volumes/estudio/2026", "Windows": "L:/VFX/2026", "Linux": "/mnt/estudio/2026"}


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
    envelope = {"perfiles": {"ana": {"hosts": {"ws1": _roots_por_defecto()}}}}
    ruta.write_text(json.dumps(envelope), encoding="utf-8")
    assert rutas_engine.leer_perfiles(str(ruta)) == envelope["perfiles"]


def test_leer_perfiles_envelope_sin_clave_perfiles_devuelve_vacio(tmp_path):
    ruta = tmp_path / "nuke_profiles.json"
    ruta.write_text('{"version": 1}', encoding="utf-8")
    assert rutas_engine.leer_perfiles(str(ruta)) == {}


# --- Store: guardar_perfiles --------------------------------------------------


def test_guardar_perfiles_round_trip_sin_temporales(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    store = {"ana": {"hosts": {"ws1": _roots_por_defecto()}, "default": _roots_por_defecto()}}
    rutas_engine.guardar_perfiles(ruta, store)
    assert rutas_engine.leer_perfiles(ruta) == store
    # El lock hermano persiste por diseno (D6); no debe quedar NINGUN temporal.
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json", "nuke_profiles.json.lock"]


def test_guardar_perfiles_preserva_claves_top_level_desconocidas(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": {"default": _roots_por_defecto()}})
    with open(ruta, "r", encoding="utf-8") as f:
        envelope = json.load(f)
    envelope["version"] = 2
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(envelope, f)
    rutas_engine.guardar_perfiles(ruta, {"pedro": {"default": _roots_por_defecto()}})
    with open(ruta, "r", encoding="utf-8") as f:
        envelope_final = json.load(f)
    assert envelope_final["version"] == 2
    assert "ana" in envelope_final["perfiles"]
    assert "pedro" in envelope_final["perfiles"]


def test_guardar_perfiles_mergea_hosts_sin_borrar_otros(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    inicial = {
        "ana": {"hosts": {"ws1": _roots_por_defecto()}, "default": _roots_por_defecto()},
        "pedro": {"hosts": {"ws9": _roots_por_defecto()}},
    }
    rutas_engine.guardar_perfiles(ruta, inicial)
    # Nuevo host para ana + usuario nuevo; ws1 y pedro/ws9 deben sobrevivir.
    rutas_engine.guardar_perfiles(
        ruta, {"ana": {"hosts": {"ws2": _roots_por_defecto()}}, "lucia": {"default": _roots_por_defecto()}}
    )
    store = rutas_engine.leer_perfiles(ruta)
    assert set(store["ana"]["hosts"]) == {"ws1", "ws2"}
    assert "pedro" in store and set(store["pedro"]["hosts"]) == {"ws9"}
    assert "lucia" in store


# --- Merge: _merge_perfil (kernel que usara el onboarding de G6) --------------


def test_merge_perfil_crea_usuario_con_host_y_default():
    store = {}
    rutas_engine._merge_perfil(store, "ana", "ws1", _roots_por_defecto())
    assert store["ana"]["hosts"]["ws1"] == _roots_por_defecto()
    assert store["ana"]["default"] == _roots_por_defecto()


def test_merge_perfil_conserva_otros_usuarios_y_hosts_existentes():
    store = {"pedro": {"hosts": {"ws9": _roots_por_defecto()}}}
    rutas_engine._merge_perfil(store, "ana", "ws1", _roots_por_defecto())
    rutas_engine._merge_perfil(store, "ana", "ws2", _roots_por_defecto())
    assert set(store["pedro"]["hosts"]) == {"ws9"}
    assert set(store["ana"]["hosts"]) == {"ws1", "ws2"}
    assert store["ana"]["default"] == _roots_por_defecto()


# --- crear_perfil_default -----------------------------------------------------


def test_crear_perfil_default_sin_base_usa_las_tres_roots_ficticias():
    assert rutas_engine.crear_perfil_default(None) == _roots_por_defecto()


def test_crear_perfil_default_slot_macos():
    perfil = rutas_engine.crear_perfil_default("/Volumes/estudio/2026")
    assert perfil["macOS"] == "/Volumes/estudio/2026"
    assert perfil["Windows"] == "L:/VFX/2026"
    assert perfil["Linux"] == "/mnt/estudio/2026"


def test_crear_perfil_default_slot_windows():
    perfil = rutas_engine.crear_perfil_default("L:/VFX/2026")
    assert perfil["Windows"] == "L:/VFX/2026"
    assert perfil["macOS"] == "/Volumes/estudio/2026"
    assert perfil["Linux"] == "/mnt/estudio/2026"


def test_crear_perfil_default_slot_linux():
    perfil = rutas_engine.crear_perfil_default("/mnt/estudio/2026")
    assert perfil["Linux"] == "/mnt/estudio/2026"
    assert perfil["macOS"] == "/Volumes/estudio/2026"
    assert perfil["Windows"] == "L:/VFX/2026"


def test_crear_perfil_default_forma_desconocida_conserva_las_tres():
    perfil = rutas_engine.crear_perfil_default("/raro/otro/lugar")
    assert perfil == _roots_por_defecto()


# --- Lock: _lock_clase factory (D6) -------------------------------------------


def test_lock_clase_posix_devuelve_clase_fcntl():
    assert rutas_engine._lock_clase("posix") is rutas_engine._LockFcntl
    assert rutas_engine._lock_clase("darwin") is rutas_engine._LockFcntl
    assert rutas_engine._lock_clase("linux") is rutas_engine._LockFcntl


def test_lock_clase_nt_devuelve_clase_msvcrt():
    assert rutas_engine._lock_clase("nt") is rutas_engine._LockMsvcrt
    assert rutas_engine._lock_clase("windows") is rutas_engine._LockMsvcrt


def test_lock_clase_desconocida_devuelve_noop():
    fcntl_cls = rutas_engine._lock_clase("posix")
    assert rutas_engine._lock_clase("plan9") is rutas_engine._LockNoop
    assert rutas_engine._lock_clase("") is rutas_engine._LockNoop
    assert rutas_engine._LockNoop is not fcntl_cls


def test_lock_fcntl_real_adquiere_y_libera(tmp_path):
    pytest.importorskip("fcntl")
    ruta = str(tmp_path / "perfiles.json.lock")
    with open(ruta, "a+b") as fd:
        lock = rutas_engine._lock_clase("posix")(fd)
        assert lock.intentar() is True
        # Ya liberado, un segundo acquire debe volver a funcionar (no queda preso).
        lock.liberar()
        assert lock.intentar() is True
        lock.liberar()


def test_lock_noop_nunca_bloquea(tmp_path):
    ruta = str(tmp_path / "perfiles.json.lock")
    with open(ruta, "a+b") as fd:
        lock = rutas_engine._lock_clase("plan9")(fd)
        assert lock.intentar() is True
        lock.liberar()  # no-op documentado: no debe lanzar


# --- Lock: _lock_perfiles context manager --------------------------------------


def test_lock_perfiles_usa_sibling_y_libera_al_salir(monkeypatch, tmp_path):
    instancias = []

    class LockFalsoRastreador:
        def __init__(self, fd):
            self.fd = fd
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
        assert instancias[0].fd.name == ruta + ".lock"
        assert instancias[0].liberado is False
    assert instancias[0].liberado is True
    assert os.path.exists(ruta + ".lock")


def test_lock_perfiles_agotado_lanza_timeouterror(monkeypatch, tmp_path):
    class LockAtascado:
        def __init__(self, fd):
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


# --- Concurrencia REAL (harness de runtime, D8) --------------------------------


def _worker_guardar_perfiles(ruta, usuario, hostname, bar):
    """Worker de proceso: espera la barrera y guarda SU perfil bajo lock."""
    bar.wait()
    rutas_engine.guardar_perfiles(
        ruta,
        {
            usuario: {
                "hosts": {hostname: rutas_engine.crear_perfil_default()},
                "default": rutas_engine.crear_perfil_default(),
            }
        },
    )


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="el lock fcntl POSIX (requisito de este test) no existe en Windows",
)
def test_guardar_concurrente_multiproceso_no_pierde_perfiles(tmp_path):
    """Dos procesos escriben perfiles distintos con barrera; ambos sobreviven."""
    ruta = str(tmp_path / "nuke_profiles.json")
    ctx = multiprocessing.get_context()
    bar = ctx.Barrier(2)
    p1 = ctx.Process(target=_worker_guardar_perfiles, args=(ruta, "ana", "ws1", bar))
    p2 = ctx.Process(target=_worker_guardar_perfiles, args=(ruta, "pedro", "ws2", bar))
    p1.start()
    p2.start()
    p1.join(45)
    p2.join(45)
    assert p1.exitcode == 0, f"worker ana/ws1 fallo (exitcode {p1.exitcode})"
    assert p2.exitcode == 0, f"worker pedro/ws2 fallo (exitcode {p2.exitcode})"
    store = rutas_engine.leer_perfiles(ruta)
    esperado = _roots_por_defecto()
    assert store["ana"]["hosts"]["ws1"] == esperado
    assert store["ana"]["default"] == esperado
    assert store["pedro"]["hosts"]["ws2"] == esperado
    assert store["pedro"]["default"] == esperado
    # Sin temporales: solo el store y su lock hermano (por diseno, D6).
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json", "nuke_profiles.json.lock"]


# --- G6: Emparejamiento por precedencia (D2) ----------------------------------


_ROOTS_CUSTOM = {"macOS": "/Volumes/custom/2026", "Windows": "L:/CUSTOM/2026", "Linux": "/mnt/custom/2026"}


def test_emparejar_perfil_par_exacto_gana_sobre_default():
    perfiles = {"ana": {"hosts": {"ws1": _ROOTS_CUSTOM}, "default": _roots_por_defecto()}}
    match = rutas_engine._emparejar_perfil("ana", "ws1", perfiles)
    assert match == _ROOTS_CUSTOM
    assert set(match.keys()) == {"macOS", "Windows", "Linux"}  # misma forma (D2)


def test_emparejar_perfil_fallback_user_only():
    # spec: store que contiene solo al usuario "ana" (sin hosts)
    perfiles = {"ana": {"default": _roots_por_defecto()}}
    match = rutas_engine._emparejar_perfil("ana", "otra-maquina", perfiles)
    assert match == _roots_por_defecto()
    assert set(match.keys()) == {"macOS", "Windows", "Linux"}


def test_emparejar_perfil_hostname_only_primer_usuario_por_orden_documento():
    roots_pedro = {"macOS": "/Volumes/pedro/2026", "Windows": "L:/PEDRO/2026", "Linux": "/mnt/pedro/2026"}
    roots_lucia = {"macOS": "/Volumes/lucia/2026", "Windows": "L:/LUCIA/2026", "Linux": "/mnt/lucia/2026"}
    perfiles = {
        "pedro": {"hosts": {"ws9": roots_pedro}},
        "lucia": {"hosts": {"ws9": roots_lucia}},
    }
    match = rutas_engine._emparejar_perfil("nadie", "ws9", perfiles)
    assert match == roots_pedro  # primero en orden de documento (D2)
    assert set(match.keys()) == {"macOS", "Windows", "Linux"}


def test_emparejar_perfil_desconocido_devuelve_marcador_none():
    assert rutas_engine._emparejar_perfil("nadie", "pc99", {}) is None
    # usuario existente pero sin el host ni default: tampoco hay match
    perfiles = {"ana": {"hosts": {"ws1": _roots_por_defecto()}}}
    assert rutas_engine._emparejar_perfil("ana", "pc99", perfiles) is None


# --- G6: resolver_perfil (spec: resolution by user/hostname) ------------------


def test_resolver_perfil_par_conocido_devuelve_roots(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(
        ruta, {"ana": {"hosts": {"ws1": _roots_por_defecto()}, "default": _roots_por_defecto()}}
    )
    assert rutas_engine.resolver_perfil("ana", "ws1", ruta) == _roots_por_defecto()


def test_resolver_perfil_fallback_user_only(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": {"default": _roots_por_defecto()}})
    assert rutas_engine.resolver_perfil("ana", "otra-maquina", ruta) == _roots_por_defecto()


def test_resolver_perfil_onboarding_crea_persiste_y_segundo_resolve(tmp_path):
    """Spec: store sin 'nuevo'/'pc9' y path escribible → onboarding sin raise."""
    ruta = str(tmp_path / "nuke_profiles.json")
    roots = rutas_engine.resolver_perfil("nuevo", "pc9", ruta)
    assert roots == _roots_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["hosts"]["pc9"] == _roots_por_defecto()
    assert store["nuevo"]["default"] == _roots_por_defecto()
    # espec: "a later resolver_perfil for that pair MUST return it"
    assert rutas_engine.resolver_perfil("nuevo", "pc9", ruta) == _roots_por_defecto()


def test_resolver_perfil_determinismo_mismos_inputs_mismos_outputs(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"ana": {"hosts": {"ws1": _roots_por_defecto()}}})
    r1 = rutas_engine.resolver_perfil("ana", "ws1", ruta)
    r2 = rutas_engine.resolver_perfil("ana", "ws1", ruta)
    assert r1 == r2 == _roots_por_defecto()


# --- G6: asegurar_perfil (onboarding bajo lock, D3) ---------------------------


def test_asegurar_perfil_crea_y_devuelve_roots(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    roots = rutas_engine.asegurar_perfil("lucia", "ws2", ruta)
    assert roots == _roots_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store["lucia"]["hosts"]["ws2"] == _roots_por_defecto()
    assert store["lucia"]["default"] == _roots_por_defecto()


def test_asegurar_perfil_base_inyectada_rellena_slot_linux(tmp_path):
    ruta = str(tmp_path / "nuke_profiles.json")
    roots = rutas_engine.asegurar_perfil("rafa", "ws3", ruta, base="/mnt/estudio/2027")
    esperado = {"macOS": "/Volumes/estudio/2026", "Windows": "L:/VFX/2026", "Linux": "/mnt/estudio/2027"}
    assert roots == esperado
    store = rutas_engine.leer_perfiles(ruta)
    assert store["rafa"]["hosts"]["ws3"] == esperado
    assert store["rafa"]["default"] == esperado


def test_asegurar_perfil_carrera_ganada_devuelve_existente_sin_reescribir(tmp_path):
    """Carrera simulada: el otro proceso ya creo el perfil entre nuestra lectura y el lock.

    El re-read bajo lock encuentra el match y devuelve el perfil del ganador SIN
    reescribir: nada de roots ficticias por encima ni 'default' anadido ajeno.
    """
    ruta = str(tmp_path / "nuke_profiles.json")
    rutas_engine.guardar_perfiles(ruta, {"nuevo": {"hosts": {"pc9": _ROOTS_CUSTOM}}})
    roots = rutas_engine.asegurar_perfil("nuevo", "pc9", ruta)
    assert roots == _ROOTS_CUSTOM  # el ganador, no el default ficticio
    store = rutas_engine.leer_perfiles(ruta)
    assert store["nuevo"]["hosts"] == {"pc9": _ROOTS_CUSTOM}
    assert "default" not in store["nuevo"]  # sin rewrite: nada ajeno se agrego


# --- G6: ruta_para_plataforma (tri-platform mapping) --------------------------


@pytest.mark.parametrize("so", ["macOS", "Windows", "Linux"])
def test_ruta_para_plataforma_cada_plataforma(so):
    perfil = _roots_por_defecto()
    assert rutas_engine.ruta_para_plataforma(perfil, so) == perfil[so]


def test_ruta_para_plataforma_plataforma_ausente_devuelve_none():
    perfil = {"macOS": "/Volumes/estudio/2026", "Windows": "L:/VFX/2026"}  # sin Linux
    assert rutas_engine.ruta_para_plataforma(perfil, "Linux") is None
    assert rutas_engine.ruta_para_plataforma(perfil, "Solaris") is None


# --- G6: Concurrencia REAL de onboarding (carrera mismo par, D3) ---------------


def _worker_resolver_perfil(ruta, usuario, hostname, bar, cola):
    """Worker de proceso: espera la barrera y resuelve (onbordea si hace falta)."""
    try:
        bar.wait()
        cola.put(rutas_engine.resolver_perfil(usuario, hostname, ruta))
    except Exception as exc:  # pragma: no cover - el padre falla con el objeto
        cola.put(exc)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="el lock fcntl POSIX (requisito de este test) no existe en Windows",
)
def test_onboarding_concurrente_mismo_par_no_duplica(tmp_path):
    """Dos procesos onbordean el MISMO par sobre store vacio con barrera.

    El perdedor de la carrera read→lock→write relee bajo lock, encuentra el
    perfil del ganador y lo devuelve: el store final tiene EXACTAMENTE un
    ``nuevo``/``pc9`` (sin duplicados ni pisados) y sin temporales.
    """
    ruta = str(tmp_path / "nuke_profiles.json")
    ctx = multiprocessing.get_context()
    bar = ctx.Barrier(2)
    cola = ctx.Queue()
    p1 = ctx.Process(target=_worker_resolver_perfil, args=(ruta, "nuevo", "pc9", bar, cola))
    p2 = ctx.Process(target=_worker_resolver_perfil, args=(ruta, "nuevo", "pc9", bar, cola))
    p1.start()
    p2.start()
    p1.join(45)
    p2.join(45)
    assert p1.exitcode == 0, f"worker 1 fallo (exitcode {p1.exitcode})"
    assert p2.exitcode == 0, f"worker 2 fallo (exitcode {p2.exitcode})"
    r1 = cola.get(timeout=10)
    r2 = cola.get(timeout=10)
    assert isinstance(r1, dict) and isinstance(r2, dict), f"worker devolvio excepcion: {r1!r} {r2!r}"
    assert r1 == r2 == _roots_por_defecto()
    store = rutas_engine.leer_perfiles(ruta)
    assert store == {"nuevo": {"hosts": {"pc9": _roots_por_defecto()}, "default": _roots_por_defecto()}}
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["nuke_profiles.json", "nuke_profiles.json.lock"]