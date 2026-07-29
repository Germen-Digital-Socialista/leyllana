"""Ajustes: motor, modelo, CLI de suscripcion y apariencia.

Lo que se guarda aqui va a ``leyllana.toml``, el mismo archivo que lee la CLI
(ADR 0021), y el dialogo dice cual es esa ruta para que no haya misterio sobre
que se esta editando.

``a_config`` es puro: toma los valores de los campos y devuelve una ``Config``.
Eso deja la parte que de verdad puede equivocarse fuera de la ventana y probable
sin ella.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import CliConfig, Config, EngineConfig, GuiConfig, ModelConfig
from ..engine.cli_provider import PRESETS
from . import theme

# Los proveedores por API key existen en el registro pero todavia no estan
# implementados (ADR 0004), asi que no se ofrecen aqui: un desplegable que
# permite elegir algo que siempre falla no es una opcion, es una trampa.
_PROVEEDORES = (
    ("Local (no sale nada de su equipo)", "local"),
    ("CLI de suscripcion (el documento sale de su equipo)", "cli"),
)

_GPU = (
    ("Automatico (usa GPU si hay)", "auto"),
    ("Solo CPU", "cpu"),
    ("Forzar GPU", "gpu"),
)

_TEMAS = (
    ("Seguir al sistema", theme.SISTEMA),
    ("Claro", theme.CLARO),
    ("Oscuro", theme.OSCURO),
)


class SettingsDialog(QDialog):
    """Edita la config y la devuelve; guardarla es cosa de quien lo abrio."""

    def __init__(self, config: Config, config_path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._config = config

        raiz = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._pestana_motor(), "Motor")
        tabs.addTab(self._pestana_local(), "Modelo local")
        tabs.addTab(self._pestana_cli(), "CLI de suscripcion")
        tabs.addTab(self._pestana_apariencia(), "Apariencia")
        raiz.addWidget(tabs)

        pie = QLabel(f"Se guarda en: {config_path}")
        pie.setWordWrap(True)
        raiz.addWidget(pie)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        raiz.addWidget(botones)

        self._cargar(config)

    # --------------------------------------------------------------- montaje

    def _pestana_motor(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.proveedor = QComboBox()
        for etiqueta, valor in _PROVEEDORES:
            self.proveedor.addItem(etiqueta, valor)
        f.addRow("Motor:", self.proveedor)

        self.temperatura = QDoubleSpinBox()
        self.temperatura.setRange(0.0, 1.0)
        self.temperatura.setSingleStep(0.05)
        self.temperatura.setToolTip(
            "Baja = mas literal. Subirla aumenta el riesgo de que el modelo "
            "invente, que es justo lo que esta herramienta no debe hacer."
        )
        f.addRow("Temperatura:", self.temperatura)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(128, 32768)
        self.max_tokens.setSingleStep(128)
        f.addRow("Largo maximo de la respuesta:", self.max_tokens)
        return w

    def _pestana_local(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.server_path, fila_srv = _campo_con_examinar(
            self, "Binario llama-server", "Ejecutables (*.exe);;Todos los archivos (*)"
        )
        f.addRow("llama-server:", fila_srv)

        self.modelo_path, fila_mod = _campo_con_examinar(
            self, "Modelo GGUF", "Modelos GGUF (*.gguf);;Todos los archivos (*)"
        )
        f.addRow("Modelo por defecto:", fila_mod)

        self.modelo_ctx = QSpinBox()
        self.modelo_ctx.setRange(512, 262144)
        self.modelo_ctx.setSingleStep(512)
        self.modelo_ctx.setToolTip(
            "Un contexto mas grande trocea menos el documento y da una lectura "
            "mas completa, a cambio de mas RAM."
        )
        f.addRow("Contexto (tokens):", self.modelo_ctx)

        self.gpu = QComboBox()
        for etiqueta, valor in _GPU:
            self.gpu.addItem(etiqueta, valor)
        f.addRow("GPU:", self.gpu)

        self.threads = QSpinBox()
        self.threads.setRange(0, 256)
        self.threads.setSpecialValueText("Automatico")
        f.addRow("Hilos de CPU:", self.threads)
        return w

    def _pestana_cli(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        aviso = QLabel(
            "Este camino saca el documento de su equipo. Se le pedira "
            "confirmacion en cada explicacion."
        )
        aviso.setWordWrap(True)
        v.addWidget(aviso)

        f = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem("(ninguno)", "")
        for nombre in sorted(PRESETS):
            self.preset.addItem(nombre, nombre)
        self.preset.setToolTip("Presets verificados de punta a punta.")
        f.addRow("Preset:", self.preset)

        self.command = QLineEdit()
        self.command.setPlaceholderText("codex exec -")
        self.command.setToolTip(
            "Argv completo de otro agente CLI, separado por espacios. Si lo "
            "llena, gana sobre el preset."
        )
        f.addRow("Comando propio:", self.command)

        self.cli_model = QLineEdit()
        self.cli_model.setPlaceholderText("claude-sonnet-4-6")
        f.addRow("Modelo:", self.cli_model)

        self.cli_timeout = QDoubleSpinBox()
        self.cli_timeout.setRange(10.0, 7200.0)
        self.cli_timeout.setSuffix(" s")
        f.addRow("Timeout:", self.cli_timeout)

        self.cli_ctx = QSpinBox()
        self.cli_ctx.setRange(1000, 2_000_000)
        self.cli_ctx.setSingleStep(1000)
        f.addRow("Contexto del modelo (tokens):", self.cli_ctx)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _pestana_apariencia(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.tema = QComboBox()
        for etiqueta, valor in _TEMAS:
            self.tema.addItem(etiqueta, valor)
        f.addRow("Tema:", self.tema)

        self.cuerpo = QSpinBox()
        self.cuerpo.setRange(8, 32)
        self.cuerpo.setSuffix(" pt")
        f.addRow("Tamano de letra del resultado:", self.cuerpo)
        return w

    # ----------------------------------------------------------------- datos

    def _cargar(self, config: Config) -> None:
        e = config.engine
        _seleccionar(self.proveedor, e.provider)
        self.temperatura.setValue(e.temperature)
        self.max_tokens.setValue(e.max_tokens)
        self.server_path.setText(e.server_path or "")
        self.modelo_path.setText(e.default_model.path or "")
        self.modelo_ctx.setValue(e.default_model.ctx)
        _seleccionar(self.gpu, e.gpu)
        self.threads.setValue(e.threads)
        _seleccionar(self.preset, e.cli.preset or "")
        self.command.setText(" ".join(e.cli.command))
        self.cli_model.setText(e.cli.model or "")
        self.cli_timeout.setValue(e.cli.timeout)
        self.cli_ctx.setValue(e.cli.ctx_tokens)
        _seleccionar(self.tema, config.gui.theme)
        self.cuerpo.setValue(config.gui.font_size)

    def a_config(self) -> Config:
        """Devuelve la ``Config`` con lo que quedo en los campos.

        Un campo de texto vacio vuelve como ``None``, no como cadena vacia: es la
        diferencia entre "sin configurar" y "configurado con nada", y la segunda
        haria fallar al proveedor con un mensaje sin sentido.
        """
        base = self._config.engine
        motor = EngineConfig(
            provider=self.proveedor.currentData(),
            default_model=ModelConfig(
                path=_o_none(self.modelo_path.text()), ctx=self.modelo_ctx.value()
            ),
            fallback_model=base.fallback_model,
            cli=CliConfig(
                preset=_o_none(self.preset.currentData()),
                command=tuple(self.command.text().split()),
                model=_o_none(self.cli_model.text()),
                timeout=self.cli_timeout.value(),
                ctx_tokens=self.cli_ctx.value(),
            ),
            server_path=_o_none(self.server_path.text()),
            gpu=self.gpu.currentData(),
            temperature=self.temperatura.value(),
            max_tokens=self.max_tokens.value(),
            threads=self.threads.value(),
        )
        gui = GuiConfig(theme=self.tema.currentData(), font_size=self.cuerpo.value())
        return replace(self._config, engine=motor, gui=gui)


def _o_none(texto: str | None) -> str | None:
    limpio = (texto or "").strip()
    return limpio or None


def _seleccionar(combo: QComboBox, valor) -> None:
    """Selecciona por dato; si el valor del archivo no esta, deja el primero."""
    indice = combo.findData(valor)
    combo.setCurrentIndex(indice if indice >= 0 else 0)


def _campo_con_examinar(padre: QWidget, titulo: str, filtro: str):
    """Un campo de ruta con su boton Examinar, devueltos como (campo, fila)."""
    campo = QLineEdit()
    contenedor = QWidget()
    fila = QHBoxLayout(contenedor)
    fila.setContentsMargins(0, 0, 0, 0)
    boton = QPushButton("Examinar...")

    def elegir() -> None:
        ruta, _ = QFileDialog.getOpenFileName(padre, titulo, campo.text(), filtro)
        if ruta:
            campo.setText(ruta)

    boton.clicked.connect(elegir)
    fila.addWidget(campo, 1)
    fila.addWidget(boton)
    return campo, contenedor


__all__ = ["SettingsDialog"]
