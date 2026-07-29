"""Tests de la capa GUI (ADR 0002).

Se salta entero si PySide6 no esta instalado: la interfaz es un extra, no parte
del paquete base. Los widgets se crean sobre la plataforma ``offscreen``, sin
ventana real.

Aqui no se comprueban pixeles. Se comprueba lo que de verdad puede estar mal: el
tema que se resuelve, el Markdown que se compone, el error que se muestra, la
fuente que se arma para el engine, y que la sesion mantenga un solo proveedor.
"""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from leyllana.config import CliConfig, Config, EngineConfig, GuiConfig  # noqa: E402
from leyllana.engine import ConsentRequired, ParseError  # noqa: E402
from leyllana.engine.base import ProviderError  # noqa: E402
from leyllana.gui import theme  # noqa: E402
from leyllana.gui.errors import mensaje  # noqa: E402
from leyllana.gui.result_panel import ResultPanel, componer  # noqa: E402
from leyllana.gui.session import Session  # noqa: E402
from leyllana.gui.source_panel import SourcePanel  # noqa: E402
from leyllana.gui.terminal_panel import limpiar_ansi  # noqa: E402
from leyllana.input.validation import ExtractionError  # noqa: E402
from leyllana.types import Explanation, Nivel, SourceInfo  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------- temas


@pytest.mark.parametrize(
    ("configurado", "sistema_oscuro", "esperado"),
    [
        ("claro", True, "claro"),
        ("oscuro", False, "oscuro"),
        ("sistema", True, "oscuro"),
        ("sistema", False, "claro"),
        ("", False, "claro"),
        ("  OSCURO  ", False, "oscuro"),
        # Un valor invalido editado a mano no puede tumbar la ventana.
        ("fucsia", False, "claro"),
    ],
)
def test_resolver_tema(configurado, sistema_oscuro, esperado):
    assert theme.resolver(configurado, sistema_oscuro) == esperado


def _luminancia(hexa: str) -> float:
    """Luminancia relativa de un color #rrggbb, segun la formula de WCAG."""
    canales = []
    for i in (1, 3, 5):
        c = int(hexa[i : i + 2], 16) / 255
        canales.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


@pytest.mark.parametrize("tema", [theme.CLARO, theme.OSCURO])
@pytest.mark.parametrize(
    ("frente", "fondo", "minimo"),
    [
        ("text", "base", 4.5),  # texto normal: WCAG AA
        ("text", "window", 4.5),
        ("dim", "base", 3.0),  # texto secundario: al menos AA grande
        ("highlight_text", "highlight", 4.5),
    ],
)
def test_el_contraste_alcanza_para_leer_un_rato_largo(tema, frente, fondo, minimo):
    # El requisito del PRD no es que se vea bonito, es que se pueda leer un texto
    # legal de corrido. Sin esta comprobacion, un retoque de paleta lo rompe sin
    # que nada avise.
    assert _contraste(theme.color(tema, frente), theme.color(tema, fondo)) >= minimo


# ------------------------------------------------------------------ errores


@pytest.mark.parametrize(
    ("exc", "trozo"),
    [
        (ConsentRequired("saldria hacia claude"), "saldria hacia claude"),
        (ExtractionError("pdf vacio"), "Entrada no utilizable"),
        (ParseError("faltan secciones"), "Respuesta del modelo no valida"),
        (NotImplementedError("api key"), "aun no disponible"),
        (ProviderError("no arranco"), "No se pudo generar"),
        (FileNotFoundError("no esta"), "Error:"),
        (ValueError("mal"), "Error:"),
        (RuntimeError("raro"), "Error inesperado"),
    ],
)
def test_cada_fallo_del_engine_tiene_su_aviso(exc, trozo):
    assert trozo in mensaje(exc)


def test_el_aviso_de_consentimiento_va_tal_cual():
    # Sin encabezado agregado: el texto de ADR 0013 ya explica el envio entero.
    texto = "Este envio saca el documento de su equipo hacia claude."
    assert mensaje(ConsentRequired(texto)) == texto


# ------------------------------------------------------------- composicion


def _explicacion() -> Explanation:
    return Explanation(
        que_hace="Regula algo.",
        a_quien_afecta="A los organismos.",
        articulos_clave="Articulo 1.",
        en_una_frase="Una ley.",
    )


def test_componer_es_lo_mismo_que_imprime_la_cli():
    info = SourceInfo(titulo="Ley 21.663", url="https://ejemplo.cl")
    exp = _explicacion()
    assert componer(exp, info) == info.to_markdown() + "\n" + exp.to_markdown()


def test_sin_datos_de_fuente_no_se_inventa_el_bloque():
    exp = _explicacion()
    salida = componer(exp, SourceInfo())
    assert salida == exp.to_markdown()
    assert "## Fuente" not in salida


def test_el_disclaimer_siempre_va(app):
    panel = ResultPanel()
    panel.mostrar(_explicacion(), SourceInfo())
    assert "no es asesoria legal" in panel.vista.toPlainText().lower()


def test_exportar_esta_apagado_hasta_que_hay_resultado(app):
    panel = ResultPanel()
    assert not panel.boton_exportar.isEnabled()
    panel.mostrar(_explicacion(), SourceInfo())
    assert panel.boton_exportar.isEnabled()
    panel.limpiar()
    assert not panel.boton_exportar.isEnabled()


# ------------------------------------------------------------ panel fuente


def test_la_fuente_se_arma_como_la_espera_el_engine(app):
    panel = SourcePanel()

    panel.tabs.setCurrentIndex(0)
    panel.ruta.setText("  C:/leyes/ley.pdf  ")
    assert panel.source() == "C:/leyes/ley.pdf"

    panel.tabs.setCurrentIndex(1)
    panel.pegado.setPlainText("Articulo 1. Texto.")
    assert panel.source() == "paste:Articulo 1. Texto."

    panel.tabs.setCurrentIndex(2)
    panel.url.setText("https://www.bcn.cl/leychile/navegar?idNorma=1")
    assert panel.source() == "https://www.bcn.cl/leychile/navegar?idNorma=1"


@pytest.mark.parametrize("pestana", [0, 1, 2])
def test_una_fuente_vacia_se_avisa_antes_de_llamar_al_engine(app, pestana):
    panel = SourcePanel()
    panel.tabs.setCurrentIndex(pestana)
    with pytest.raises(ValueError):
        panel.source()


def test_el_nivel_devuelve_el_valor_del_dominio(app):
    panel = SourcePanel()
    assert panel.nivel_elegido() is Nivel.PUBLICO
    panel.nivel.setCurrentIndex(1)
    assert panel.nivel_elegido() is Nivel.TECNICO


def test_la_barra_solo_muestra_porcentaje_cuando_hay_fragmentos(app):
    from leyllana.engine.progress import Progress, Stage

    panel = SourcePanel()
    panel.avanzar(Progress(Stage.GENERANDO))
    assert (panel.barra.minimum(), panel.barra.maximum()) == (0, 0)  # indeterminada

    panel.avanzar(Progress(Stage.ANALIZANDO, 3, 13))
    assert panel.barra.maximum() == 13
    assert panel.barra.value() == 3
    assert "3 de 13" in panel.etiqueta_estado.text()


def test_cancelar_solo_esta_activo_durante_una_corrida(app):
    panel = SourcePanel()
    assert not panel.boton_cancelar.isEnabled()
    panel.comenzar()
    assert panel.boton_cancelar.isEnabled()
    assert not panel.boton_explicar.isEnabled()
    panel.terminar("Cancelado.")
    assert not panel.boton_cancelar.isEnabled()
    assert panel.boton_explicar.isEnabled()


# ----------------------------------------------------------------- sesion


class _FakeProvider:
    sends_to_cloud = True
    destino = "el CLI configurado"

    def __init__(self):
        self.cerrado = False

    def generate(self, prompt, *, cancel=None):
        return ""

    def close(self):
        self.cerrado = True


def _sesion_con(fake, monkeypatch, config=None):
    monkeypatch.setattr(
        "leyllana.gui.session.get_provider", lambda cfg, trace=None: fake
    )
    return Session(config or Config())


def test_el_proveedor_se_construye_una_sola_vez(monkeypatch):
    creados = []

    def crear(cfg, trace=None):
        creados.append(cfg)
        return _FakeProvider()

    monkeypatch.setattr("leyllana.gui.session.get_provider", crear)
    sesion = Session(Config())
    primero = sesion.provider
    assert sesion.provider is primero  # el modelo no se recarga por corrida
    assert len(creados) == 1


def test_cambiar_la_config_suelta_el_proveedor(monkeypatch):
    fake = _FakeProvider()
    sesion = _sesion_con(fake, monkeypatch)
    assert sesion.provider is not None
    sesion.update_config(Config(engine=EngineConfig(provider="cli")))
    assert fake.cerrado
    assert sesion.config.engine.provider == "cli"


def test_cambiar_solo_la_letra_no_recarga_el_modelo(monkeypatch):
    fake = _FakeProvider()
    sesion = _sesion_con(fake, monkeypatch)
    assert sesion.provider is not None
    sesion.update_gui(GuiConfig(theme="oscuro", font_size=20))
    assert not fake.cerrado  # agrandar la letra no cuesta minutos de recarga
    assert sesion.config.gui.font_size == 20


def test_la_sesion_expone_si_el_envio_sale_del_equipo(monkeypatch):
    sesion = _sesion_con(
        _FakeProvider(),
        monkeypatch,
        Config(engine=EngineConfig(provider="cli", cli=CliConfig(preset="claude"))),
    )
    assert sesion.envia_a_la_nube
    assert sesion.destino == "el CLI configurado"


def test_cerrar_la_sesion_libera_el_modelo(monkeypatch):
    fake = _FakeProvider()
    sesion = _sesion_con(fake, monkeypatch)
    assert sesion.provider is not None
    sesion.close()
    assert fake.cerrado


# --------------------------------------------------------------- terminal


@pytest.mark.parametrize(
    ("crudo", "limpio"),
    [
        ("\x1b[32mverde\x1b[0m", "verde"),
        ("\x1b]0;titulo\x07hola", "hola"),
        ("linea\r\notra", "linea\notra"),
        ("beep\x07", "beep"),
        ("sin escapes", "sin escapes"),
    ],
)
def test_la_terminal_deja_texto_legible(crudo, limpio):
    assert limpiar_ansi(crudo) == limpio


# --------------------------------- la traza en el panel de terminal (ADR 0022)


def _eventos_de_una_corrida_de_nube():
    from leyllana.engine.trace import Kind, TraceEvent

    return [
        TraceEvent(
            Kind.INVOCACION, r"claude -p --system-prompt-file C:\tmp\system.txt"
        ),
        TraceEvent(Kind.ENVIO, "99.468 caracteres por stdin"),
        TraceEvent(Kind.RESPUESTA, "Que hace: regula algo."),
        TraceEvent(Kind.FIN, "codigo 0 en 41.2s"),
    ]


def test_el_panel_muestra_el_comando_y_el_tamano(app):
    from leyllana.gui.terminal_panel import TerminalPanel

    panel = TerminalPanel()
    for ev in _eventos_de_una_corrida_de_nube():
        panel.registrar(ev)
    texto = panel.vista.toPlainText()

    assert "claude -p --system-prompt-file" in texto
    assert "99.468 caracteres" in texto
    assert "sale del equipo" in texto
    assert "codigo 0 en 41.2s" in texto
    # Lo que hizo la app va marcado, para no confundirlo con lo que tecleo el usuario.
    assert "leyllana>" in texto
    panel.cerrar()


def test_el_panel_sigue_sirviendo_sin_shell(app, monkeypatch):
    # Sin pywinpty el panel no se cae ni se vacia: es donde se ve lo que sale.
    import leyllana.gui.terminal_panel as tp

    monkeypatch.setattr(tp.sys, "platform", "linux")
    panel = tp.TerminalPanel()
    assert panel.vista.isVisibleTo(panel)
    assert "pywinpty" in panel.vista.toPlainText()

    for ev in _eventos_de_una_corrida_de_nube():
        panel.registrar(ev)
    assert "99.468 caracteres" in panel.vista.toPlainText()
    panel.cerrar()


def test_la_sesion_pasa_el_sumidero_al_proveedor_de_nube(monkeypatch):
    visto = {}

    def crear(cfg, trace=None):
        visto["trace"] = trace
        return _FakeProvider()

    monkeypatch.setattr("leyllana.gui.session.get_provider", crear)
    sesion = Session(Config())
    sumidero = lambda ev: None  # noqa: E731
    sesion.set_trace(sumidero)
    assert sesion.provider is not None
    assert visto["trace"] is sumidero


def test_cambiar_el_sumidero_suelta_el_proveedor_viejo(monkeypatch):
    # Si no, quedaria uno enviando sin dejar rastro en el panel.
    fake = _FakeProvider()
    sesion = _sesion_con(fake, monkeypatch)
    assert sesion.provider is not None
    sesion.set_trace(lambda ev: None)
    assert fake.cerrado
