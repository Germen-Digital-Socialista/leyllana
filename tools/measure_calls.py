"""Mide una sola llamada al ``llama-server`` en una configuracion dada.

Herramienta de desarrollo, no parte de la aplicacion. Sirve para comparar builds,
ctx y banderas en minutos en vez de esperar una corrida completa: arranca el binario
que se le indique, le manda un prompt del tamano que se le indique y reporta el
rendimiento que el propio servidor declara en su bloque ``timings``.

Reporta lo que hace falta para decidir si una configuracion es viable:

- que dispositivos ve el binario (un build sin backend de GPU no ve ninguno);
- si el contexto cabe, o si muere al arrancar por falta de memoria, con el error;
- tokens por segundo de prompt (prefill) y de generacion, que se degradan los dos
  a medida que el contexto se hace mas profundo;
- RAM del proceso y VRAM ocupada.

Ejemplos:

    uv run python tools/measure_calls.py --doc ley.txt --ctx 4096 --chars 8652
    uv run python tools/measure_calls.py --doc ley.txt --ctx 16384 --chars 51660 \
        --server C:/ruta/llama-server.exe --flags "-fa on -ctk q8_0 -ctv q8_0"
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from leyllana.config import load

# Lineas del log que explican por que una configuracion anda como anda o no arranca.
_INTERESANTES = (
    "device",
    "vulkan",
    "cuda",
    "offload",
    "buffer",
    "n_ctx",
    "kv",
    "flash",
    "error",
    "failed",
    "warn",
    "memory",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="measure_calls",
        description="Mide una llamada al llama-server en una configuracion dada.",
    )
    p.add_argument("--doc", required=True, help="texto de donde sacar el prompt")
    p.add_argument(
        "--chars", type=int, required=True, help="caracteres de prompt a enviar"
    )
    p.add_argument("--ctx", type=int, required=True, help="ctx del servidor")
    p.add_argument("--config", default=None, help="ruta a leyllana.toml")
    p.add_argument("--model", default=None, help="GGUF a usar en vez del configurado")
    p.add_argument("--server", default=None, help="binario en vez del configurado")
    p.add_argument("--flags", default="", help="banderas extra, entre comillas")
    p.add_argument("--max-tokens", type=int, default=64, help="tokens a generar")
    p.add_argument("--out", default="mediciones", help="carpeta para el log")
    return p.parse_args()


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _vram_mib() -> str:
    """VRAM ocupada segun nvidia-smi, o el motivo de no saberlo."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return out.stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        return f"sin nvidia-smi ({exc})"


def _working_set_mib(pid: int) -> float:
    """RAM residente del proceso, o -1 si no se pudo consultar."""
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {pid}).WorkingSet64",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return int(out.stdout.strip()) / 1024**2
    except (OSError, subprocess.SubprocessError, ValueError):
        return -1.0


def _dispositivos(binario: Path) -> str:
    """Lo que el binario dice ver. Un build sin backend de GPU no lista ninguno."""
    try:
        out = subprocess.run(
            [str(binario), "--list-devices"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=str(binario.parent),
        )
        # Se descarta el encabezado ("Available devices:"): sin esto un build sin
        # backend de GPU imprime solo el titulo y parece que hubiera listado algo,
        # que es exactamente el error que esta linea existe para evitar.
        lineas = [
            ln.strip()
            for ln in out.stdout.splitlines()
            if ln.strip() and not ln.rstrip().endswith(":")
        ]
        return "; ".join(lineas) if lineas else "(ninguno: build sin backend de GPU)"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"no se pudo consultar ({exc})"


def _esperar_salud(proc: subprocess.Popen, base: str, limite: float) -> str:
    """Espera a que el servidor responda /health. Devuelve '' si quedo listo."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite:
        if proc.poll() is not None:
            return f"el servidor murio al arrancar (codigo {proc.returncode})"
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as r:  # noqa: S310
                if json.loads(r.read())["status"] == "ok":
                    return ""
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            time.sleep(0.5)
    return f"el servidor no quedo listo en {limite:.0f}s"


def _cola_del_log(log: Path, lineas: int) -> None:
    texto = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for ln in texto[-lineas:]:
        print("   " + ln.strip()[:170])


def _relevantes_del_log(log: Path) -> None:
    texto = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for ln in texto:
        if any(k in ln.lower() for k in _INTERESANTES):
            print("   " + ln.strip()[:170])


def main() -> int:
    args = _parse_args()
    cfg = load(args.config).engine
    binario = Path(args.server or cfg.server_path or "")
    modelo = Path(args.model or cfg.default_model.path or "")
    if not binario.is_file():
        print(f"no existe el binario: {binario}")
        return 2
    if not modelo.is_file():
        print(f"no existe el modelo: {modelo}")
        return 2

    salida = Path(args.out)
    salida.mkdir(parents=True, exist_ok=True)
    banderas = args.flags.split()
    texto = Path(args.doc).read_text(encoding="utf-8")[: args.chars]

    print(f"binario:      {binario}")
    print(f"dispositivos: {_dispositivos(binario)}")
    print(f"modelo:       {modelo.name}")
    print(f"ctx:          {args.ctx}")
    print(f"banderas:     {' '.join(banderas) or '(ninguna)'}")
    print(f"prompt:       {len(texto)} caracteres")
    print(f"VRAM antes:   {_vram_mib()}")

    puerto = _puerto_libre()
    base = f"http://127.0.0.1:{puerto}"
    log = salida / f"calls-c{args.ctx}-{puerto}.log"
    argv = [
        str(binario),
        "-m", str(modelo),
        "--host", "127.0.0.1",
        "--port", str(puerto),
        "-c", str(args.ctx),
        "-ngl", "999",
        "--jinja",
        *banderas,
    ]

    with log.open("wb") as fh:
        t0 = time.monotonic()
        proc = subprocess.Popen(argv, cwd=str(binario.parent), stdout=fh, stderr=fh)
        problema = _esperar_salud(proc, base, 300.0)
        if problema:
            print(f"\n{problema}")
            fh.flush()
            _cola_del_log(log, 12)
            if proc.poll() is None:
                proc.kill()
            return 1
        print(f"arranque:     {time.monotonic() - t0:.1f}s")
        print(f"VRAM cargado: {_vram_mib()}")
        print(f"RAM proceso:  {_working_set_mib(proc.pid):.0f} MiB")

        payload = json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "Resume en una frase:\n\n" + texto}
                ],
                "max_tokens": args.max_tokens,
                "temperature": cfg.temperature,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        ).encode()
        req = urllib.request.Request(
            f"{base}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t1 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:  # noqa: S310
                obj = json.loads(r.read())
            dur = time.monotonic() - t1
            tim = obj.get("timings", {})
            print(f"\nllamada:      {dur:.1f}s ({dur / 60:.1f} min)")
            if tim:
                print(
                    f"  prompt: {tim.get('prompt_n')} tok en "
                    f"{tim.get('prompt_ms', 0) / 1000:.1f}s "
                    f"({tim.get('prompt_per_second', 0):.1f} tok/s)"
                )
                print(
                    f"  gen:    {tim.get('predicted_n')} tok en "
                    f"{tim.get('predicted_ms', 0) / 1000:.1f}s "
                    f"({tim.get('predicted_per_second', 0):.1f} tok/s)"
                )
            else:
                print(f"  usage: {obj.get('usage')}")
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read().decode("utf-8", "replace")
            print(f"\nHTTP {exc.code} tras {time.monotonic() - t1:.1f}s")
            print(f"  {cuerpo[:500]}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"\nla llamada fallo: {type(exc).__name__}: {exc}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    print("\n--- lineas relevantes del log del servidor ---")
    _relevantes_del_log(log)
    print(f"\nlog completo: {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
