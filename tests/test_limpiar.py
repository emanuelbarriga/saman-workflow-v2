"""
Tests de SamanTools.core.limpiar (sanitizador de texto .nk/.gizmo).

limpiar es un modulo puro (solo stdlib, NO importa nuke), asi que se testea
con pytest directo, sin stub. Este archivo porta los tests de V1
(tests/test_limpiar.py de saman-nuke-tools) neutralizados: la fuga de comp
real del estudio (EP_101_0042_comp_DGTV_V001) pasa a ser el valor ficticio
EP_100_000_comp. La regresion del Review.gizmo real (SamanTools/nodos/) se
REEMPLAZA por una muestra sintetica inline (spec core-limpiar): el gizmo del
estudio no viaja en un repositorio publico.
"""

import pytest

from SamanTools.core import limpiar


# --------------------------------------------------------------------------
# Muestra sintetica inline de regresion (reemplaza el Review.gizmo real):
# ejercita los TRES knobs volatiles + knobs legitimos, todo ficticio.
# --------------------------------------------------------------------------

MUESTRA_NK_INLINE = (
    "Read {\n"
    '  inputs 0\n'
    '  file "clip.mov"\n'
    "  colorspace DaVinci Intermediate WideGamut\n"
    "  mov64_prraw_plugin Standard\n"
    "  name Read1\n"
    "  xpos 100\n"
    "  ypos 10\n"
    "}\n"
    "Viewer {\n"
    "  render_settings_schema false\n"
    '  monitorOutNDISenderName "NukeX - EP_100_000_comp - Viewer1"\n'
    "  name Viewer1\n"
    "  frame_range 1-214\n"
    "  fps 23.976\n"
    "}\n"
)

LEGITIMOS_INLINE = (
    'file "clip.mov"',
    "colorspace DaVinci Intermediate WideGamut",
    "name Read1",
    "xpos 100",
    "ypos 10",
    "name Viewer1",
    "frame_range 1-214",
    "fps 23.976",
)


def test_muestra_inline_quita_los_tres_volatiles():
    limpio = limpiar.sanitizar_texto_nk(MUESTRA_NK_INLINE)
    assert "mov64_prraw_plugin" not in limpio
    assert "render_settings_schema" not in limpio
    assert "monitorOutNDISenderName" not in limpio


def test_muestra_inline_conserva_todo_legitimo():
    limpio = limpiar.sanitizar_texto_nk(MUESTRA_NK_INLINE)
    for dato in LEGITIMOS_INLINE:
        assert dato in limpio
    assert limpio.count("Read {") == 1
    assert limpio.count("Viewer {") == 1


def test_elimina_mov64_prraw():
    texto = (
        "Read {\n"
        '  inputs 0\n'
        '  file "clip.mov"\n'
        "  mov64_prraw_plugin Standard\n"
        "  name Read1\n"
        "}\n"
    )
    limpio = limpiar.sanitizar_texto_nk(texto)
    assert "mov64_prraw_plugin" not in limpio
    assert 'file "clip.mov"' in limpio
    assert "name Read1" in limpio


def test_elimina_render_settings_schema():
    texto = (
        "Viewer {\n"
        "  render_settings_schema false\n"
        "  name Viewer1\n"
        "}\n"
    )
    limpio = limpiar.sanitizar_texto_nk(texto)
    assert "render_settings_schema" not in limpio
    assert "name Viewer1" in limpio


def test_elimina_monitor_out():
    texto = (
        "Viewer {\n"
        '  monitorOutNDISenderName "NukeX - EP_100_000_comp - Viewer1"\n'
        "  name Viewer1\n"
        "}\n"
    )
    limpio = limpiar.sanitizar_texto_nk(texto)
    assert "monitorOutNDISenderName" not in limpio
    assert "name Viewer1" in limpio


def test_varias_ocurrencias_varios_nodos():
    texto = (
        "Read {\n"
        '  inputs 0\n'
        '  file "clip1.mov"\n'
        "  colorspace DaVinci Intermediate WideGamut\n"
        "  mov64_prraw_plugin Standard\n"
        "  name Read1\n"
        "  xpos 0\n"
        "  ypos 0\n"
        "}\n"
        "Read {\n"
        '  inputs 0\n'
        '  file "clip2.mov"\n'
        "  mov64_prraw_plugin Standard\n"
        "  name Read2\n"
        "}\n"
        "Viewer {\n"
        "  render_settings_schema false\n"
        '  monitorOutNDISenderName "NukeX - EP_100_000_comp - Viewer1"\n'
        "  name Viewer1\n"
        "  xpos 100\n"
        "  ypos 10\n"
        "}\n"
    )
    limpio = limpiar.sanitizar_texto_nk(texto)
    assert "mov64_prraw_plugin" not in limpio
    assert "render_settings_schema" not in limpio
    assert "monitorOutNDISenderName" not in limpio
    for dato in (
        'file "clip1.mov"', 'file "clip2.mov"',
        "name Read1", "name Read2",
        "colorspace DaVinci Intermediate WideGamut",
        "name Viewer1", "xpos 100", "ypos 10",
    ):
        assert dato in limpio


def test_no_toca_knobs_legitimos():
    texto = (
        "Read {\n"
        "  colorspace DaVinci Intermediate WideGamut\n"
        "  name Read1\n"
        "}\n"
    )
    assert limpiar.sanitizar_texto_nk(texto) == texto


def test_idempotente():
    texto = (
        "Read {\n"
        '  file "clip.mov"\n'
        "  mov64_prraw_plugin Standard\n"
        "  render_settings_schema false\n"
        '  monitorOutNDISenderName "NukeX - View"\n'
        "  name Read1\n"
        "}\n"
    )
    una_vez = limpiar.sanitizar_texto_nk(texto)
    assert limpiar.sanitizar_texto_nk(una_vez) == una_vez


def test_idempotente_muestra_inline():
    una_vez = limpiar.sanitizar_texto_nk(MUESTRA_NK_INLINE)
    assert limpiar.sanitizar_texto_nk(una_vez) == una_vez


def test_sanitizar_archivo_cambia(tmp_path):
    ruta = tmp_path / "comp.nk"
    ruta.write_text(
        'Read {\n  file "clip.mov"\n  mov64_prraw_plugin Standard\n  name Read1\n}\n',
        encoding="utf-8",
    )
    assert limpiar.sanitizar_archivo(str(ruta)) == 1
    contenido = ruta.read_text(encoding="utf-8")
    assert "mov64_prraw_plugin" not in contenido
    assert 'file "clip.mov"' in contenido


def test_sanitizar_archivo_sin_cambios(tmp_path):
    ruta = tmp_path / "limpio.nk"
    ruta.write_text("Viewer {\n  name Viewer1\n}\n", encoding="utf-8")
    assert limpiar.sanitizar_archivo(str(ruta)) == 0
    assert ruta.read_text(encoding="utf-8") == "Viewer {\n  name Viewer1\n}\n"


def test_sanitizar_archivo_inexistente(tmp_path):
    ruta = tmp_path / "no_existe.nk"
    with pytest.raises(FileNotFoundError):
        limpiar.sanitizar_archivo(str(ruta))


# ---------------------------------------------------------------------------
# Seguridad a prueba de corrupcion: CRLF, BOM, no-UTF-8 y escritura atomica.
# ---------------------------------------------------------------------------


def test_preserva_crlf(tmp_path):
    ruta = tmp_path / "comp.nk"
    original = (
        "Read {\r\n"
        "  mov64_prraw_plugin Standard\r\n"
        "  name Read1\r\n"
        "}\r\n"
    )
    ruta.write_bytes(original.encode("utf-8"))
    assert limpiar.sanitizar_archivo(str(ruta)) == 1
    contenido = ruta.read_bytes()
    assert b"mov64_prraw_plugin" not in contenido
    # Todas las lineas restantes conservan \r\n.
    for linea in contenido.split(b"\r\n"):
        assert b"\n" not in linea, "Salto suelto convertido: %r" % linea
    assert b"name Read1\r\n" in contenido
    assert contenido.endswith(b"}\r\n")


def test_preserva_bom(tmp_path):
    ruta = tmp_path / "comp.nk"
    original = (
        "Read {\n"
        "  mov64_prraw_plugin Standard\n"
        "  name Read1\n"
        "}\n"
    )
    ruta.write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))
    assert limpiar.sanitizar_archivo(str(ruta)) == 1
    contenido = ruta.read_bytes()
    assert contenido.startswith(b"\xef\xbb\xbf"), "Se perdio el BOM"
    texto = contenido[len(b"\xef\xbb\xbf"):].decode("utf-8")
    assert "mov64_prraw_plugin" not in texto
    assert "name Read1" in texto


def test_preserva_no_utf8(tmp_path):
    ruta = tmp_path / "comp.nk"
    original = (
        "Read {\n"
        '  file "cliente-\xe9.mov"\n'
        "  mov64_prraw_plugin Standard\n"
        "  name Read1\n"
        "}\n"
    )
    ruta.write_bytes(original.encode("latin-1"))
    assert limpiar.sanitizar_archivo(str(ruta)) == 1
    contenido = ruta.read_bytes()
    # El byte \xe9 (acento latin-1) debe conservarse intacto.
    assert b"\xe9" in contenido
    assert b"mov64_prraw_plugin" not in contenido
    assert b"name Read1" in contenido


def test_no_utf8_sin_basura_no_reescribe(tmp_path):
    ruta = tmp_path / "comp.nk"
    original = (
        "Read {\n"
        '  file "cliente-\xe9.mov"\n'
        "  name Read1\n"
        "}\n"
    )
    ruta.write_bytes(original.encode("latin-1"))
    assert limpiar.sanitizar_archivo(str(ruta)) == 0
    assert ruta.read_bytes() == original.encode("latin-1")


def test_sanitizar_carpeta_recursiva(tmp_path):
    comp = tmp_path / "comp.nk"
    comp.write_text(
        "Read {\n  mov64_prraw_plugin Standard\n  name Read1\n}\n",
        encoding="utf-8",
    )
    limpio = tmp_path / "limpio.gizmo"
    limpio.write_text("Group {\n  name G1\n}\n", encoding="utf-8")
    bytes_limpio = limpio.read_bytes()
    sub = tmp_path / "sub"
    sub.mkdir()
    viejo = sub / "viejo.nk"
    viejo.write_text(
        "Viewer {\n  render_settings_schema false\n  name Viewer1\n}\n",
        encoding="utf-8",
    )

    resultado = limpiar.sanitizar_carpeta(str(tmp_path))
    assert resultado["limpiados"] == 2
    assert resultado["sin_cambios"] == 1
    assert resultado["errores"] == []

    assert "mov64_prraw_plugin" not in comp.read_text(encoding="utf-8")
    assert "render_settings_schema" not in viejo.read_text(encoding="utf-8")
    # El gizmo limpio quedo intacto (mismos bytes que al inicio).
    assert limpio.read_bytes() == bytes_limpio


def test_sanitizar_carpeta_solo_extensiones(tmp_path):
    # Contrato: solo se cuentan y procesan .nk/.gizmo (case-insensitive). Un
    # .py con basura no se toca y tampoco se cuenta como sin_cambios.
    py = tmp_path / "basura.py"
    py.write_text("mov64_prraw_plugin Standard\n", encoding="utf-8")
    resultado = limpiar.sanitizar_carpeta(str(tmp_path))
    assert resultado == {"limpiados": 0, "sin_cambios": 0, "errores": []}
    assert py.read_text(encoding="utf-8") == "mov64_prraw_plugin Standard\n"