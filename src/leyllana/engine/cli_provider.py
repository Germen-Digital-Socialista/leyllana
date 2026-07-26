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

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import Config
from ..prompt import Prompt
from .base import ProviderError

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


class CliProvider:
    """Backend que ejecuta un agente CLI. Implementa el Protocol ``Provider``."""

    sends_to_cloud = True

    def __init__(self, config: Config) -> None:
        self._cfg = config.engine.cli

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

    def generate(self, prompt: Prompt) -> str:
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
            try:
                proc = subprocess.run(  # noqa: S603 (argv de la config, sin shell)
                    argv,
                    input=entrada,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self._cfg.timeout,
                    cwd=cwd,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ProviderError(
                    f"Fallo la llamada al CLI {argv[0]}: {exc}"
                ) from exc

        if proc.returncode != 0:
            cola = (proc.stderr or "").strip()[-_STDERR_TAIL:]
            raise ProviderError(f"El CLI termino con codigo {proc.returncode}: {cola}")
        salida = (proc.stdout or "").strip()
        if not salida:
            raise ProviderError("El CLI no devolvio texto.")
        return salida


__all__ = ["CliProvider", "PRESETS"]
