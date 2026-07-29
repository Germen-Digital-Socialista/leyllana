"""Proveedor de nube via un agente CLI de suscripcion (ADR 0018).

Maneja cualquier agente CLI (Claude Code, Kimi, ...) como subproceso: el argv sale
de la config, el prompt entra por stdin y la respuesta sale por stdout. La
autenticacion la resuelve el propio CLI contra la suscripcion del usuario, asi que
leyllana no guarda ni ve credenciales (ADR 0004). Enviar por aqui saca el documento
de la maquina y por eso exige consentimiento explicito (ADR 0013).

El prompt va por stdin, no por argv: un texto legal supera el limite de linea de
comandos de Windows.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ..config import Config
from ..prompt import Prompt
from .base import ProviderError
from .progress import Cancelled, CancelToken
from .trace import Kind, TraceFn, emit

# Argv verificado de cada CLI probado. ``{system_file}`` marca donde va la ruta
# al archivo con el system prompt; el CLI que no tenga ese flag lo recibe al
# principio del stdin.
#
# El system prompt va por archivo, nunca como argumento: en Windows el shim .cmd
# corta un argumento multilinea en el primer salto de linea, y el modelo se queda
# sin guardrail ni contrato de salida sin que nada falle de forma visible.
PRESETS: dict[str, tuple[str, ...]] = {
    # --safe-mode apaga CLAUDE.md, skills, hooks, plugins y MCP sin tocar la auth
    # de la suscripcion. (--bare tambien apagaria todo eso, pero exige
    # ANTHROPIC_API_KEY y rompe justamente el camino de suscripcion.)
    "claude": (
        "claude",
        "-p",
        "--safe-mode",
        "--tools",
        "",
        "--output-format",
        "text",
        "--system-prompt-file",
        "{system_file}",
    ),
    # --quiet = --print --output-format text --final-message-only.
    "kimi": ("kimi", "--quiet"),
}

_SYSTEM_SLOT = "{system_file}"
# Cuanto stderr se muestra cuando el CLI falla.
_STDERR_TAIL = 500
# Cada cuanto se deja de esperar al CLI para mirar si el usuario cancelo. Un
# subproceso no se puede leer a medias como un flujo de tokens (ADR 0020), asi que
# aqui la cancelacion es un sondeo: se espera un poco, se mira, se vuelve a
# esperar. Un segundo es imperceptible al lado de una llamada de nube.
_CANCEL_POLL = 1.0
# Un CLI escrito en Python usa por defecto la codepage ANSI de Windows en sus
# tuberias: recibe el texto en UTF-8 como basura y devuelve cp1252. Forzar UTF-8
# arregla las dos direcciones y no afecta a los CLI que no son Python.
_CHILD_ENV = {"PYTHONIOENCODING": "utf-8"}


class CliProvider:
    """Backend que ejecuta un agente CLI. Implementa el Protocol ``Provider``."""

    sends_to_cloud = True

    def __init__(self, config: Config, trace: TraceFn | None = None) -> None:
        self._cfg = config.engine.cli
        self._trace = trace

    @property
    def ctx_tokens(self) -> int:
        """Presupuesto de contexto del modelo detras del CLI (ADR 0017)."""
        return self._cfg.ctx_tokens

    @property
    def destino(self) -> str:
        """Nombre del CLI destino, para nombrarlo en el aviso de consentimiento."""
        if self._cfg.command:
            return self._cfg.command[0]
        return self._cfg.preset or "el CLI configurado"

    def _template(self) -> tuple[str, ...]:
        """Argv configurado: ``command`` explicito, o el preset nombrado."""
        if self._cfg.command:
            return tuple(self._cfg.command)
        preset = PRESETS.get((self._cfg.preset or "").lower())
        if preset is None:
            raise ProviderError(
                "Configure engine.cli.preset ("
                + ", ".join(sorted(PRESETS))
                + ") o engine.cli.command con el argv del CLI."
            )
        return preset

    def generate(self, prompt: Prompt, *, cancel: CancelToken | None = None) -> str:
        """Corre el CLI con ``prompt`` y devuelve su respuesta de texto."""
        template = self._template()
        usa_archivo = any(_SYSTEM_SLOT in arg for arg in template)
        entrada = prompt.user if usa_archivo else f"{prompt.system}\n\n{prompt.user}"

        binario = shutil.which(template[0])
        if binario is None:
            raise ProviderError(f"No se encontro el CLI {template[0]!r} en el PATH.")

        # cwd neutro: el agente no tiene por que ver el repo desde donde se corre
        # leyllana (varios CLI auto-aprueban sus herramientas en modo no
        # interactivo). El system prompt vive en esa misma carpeta temporal.
        with tempfile.TemporaryDirectory() as cwd:
            if usa_archivo:
                ruta = Path(cwd) / "system.txt"
                ruta.write_text(prompt.system, encoding="utf-8")
                argv = [arg.replace(_SYSTEM_SLOT, str(ruta)) for arg in template]
            else:
                argv = list(template)
            argv[0] = binario
            # ``--model`` es comun a los CLI probados; si su CLI usa otro flag,
            # deje ``model`` vacio y pongalo directamente en ``command``.
            if self._cfg.model:
                argv += ["--model", self._cfg.model]
            # Se avisa ANTES de arrancar (ADR 0022): si el CLI se cuelga o lo
            # cancelan, el usuario ya alcanzo a ver que se iba a ejecutar.
            emit(self._trace, Kind.INVOCACION, subprocess.list2cmdline(argv))
            emit(
                self._trace,
                Kind.ENVIO,
                f"{len(entrada):,} caracteres por stdin".replace(",", "."),
            )
            comenzado = time.monotonic()
            try:
                proc = subprocess.Popen(  # noqa: S603 (argv de la config, sin shell)
                    argv,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=cwd,
                    env={**os.environ, **_CHILD_ENV},
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ProviderError(
                    f"Fallo la llamada al CLI {argv[0]}: {exc}"
                ) from exc
            salida_std, salida_err = self._comunicar(proc, entrada, argv[0], cancel)

        fin = f"codigo {proc.returncode} en {time.monotonic() - comenzado:.1f}s"
        salida = (salida_std or "").strip()
        # El fin se avisa pase lo que pase, tambien cuando la corrida fracasa: un
        # envio que salio y volvio con error igual salio, y ocultarlo seria
        # justamente lo que ADR 0022 viene a arreglar.
        if proc.returncode != 0 or not salida:
            emit(self._trace, Kind.FIN, fin)
        if proc.returncode != 0:
            cola = (salida_err or "").strip()[-_STDERR_TAIL:]
            raise ProviderError(f"El CLI termino con codigo {proc.returncode}: {cola}")
        if not salida:
            raise ProviderError("El CLI no devolvio texto.")
        emit(self._trace, Kind.RESPUESTA, salida)
        emit(self._trace, Kind.FIN, fin)
        return salida

    def _comunicar(
        self,
        proc: subprocess.Popen,
        entrada: str,
        nombre: str,
        cancel: CancelToken | None,
    ) -> tuple[str, str]:
        """Espera al CLI sin quedarse sordo a la cancelacion ni al timeout.

        ``communicate`` se reintenta tras un ``TimeoutExpired`` sin perder salida
        (asi esta documentado en la stdlib), y solo la primera llamada lleva el
        stdin. Entre reintento y reintento se mira el token de cancelacion; si se
        cancelo, se mata al CLI en vez de esperar los diez minutos del timeout.
        """
        limite = time.monotonic() + self._cfg.timeout
        primera = True
        while True:
            try:
                return proc.communicate(
                    entrada if primera else None, timeout=_CANCEL_POLL
                )
            except subprocess.TimeoutExpired:
                primera = False
                if cancel is not None and cancel.is_cancelled():
                    self._matar(proc)
                    raise Cancelled(
                        "La explicacion fue cancelada por el usuario."
                    ) from None
                if time.monotonic() > limite:
                    self._matar(proc)
                    raise ProviderError(
                        f"El CLI {nombre} no respondio en "
                        f"{self._cfg.timeout:.0f}s."
                    ) from None
            except (OSError, subprocess.SubprocessError) as exc:
                self._matar(proc)
                raise ProviderError(f"Fallo la llamada al CLI {nombre}: {exc}") from exc

    @staticmethod
    def _matar(proc: subprocess.Popen) -> None:
        """Mata al CLI y recoge sus tuberias, para no dejar un huerfano escribiendo."""
        proc.kill()
        try:
            proc.communicate(timeout=_CANCEL_POLL)
        except (subprocess.SubprocessError, OSError, ValueError):
            pass


__all__ = ["CliProvider", "PRESETS"]
