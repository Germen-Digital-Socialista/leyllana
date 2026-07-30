"""Mide una corrida completa de ``explain()`` y guarda con que la hizo.

Herramienta de desarrollo, no parte de la aplicacion. Corre el codigo de produccion
tal cual (config -> LocalProvider -> explain), asi que lo que mide es lo que hace la
app y no una maqueta. Existe porque una corrida lenta no se puede diagnosticar
despues: hay que capturar los hechos mientras ocurre.

Guarda tres cosas por corrida:

- el Markdown de salida, para comprobar la fidelidad contra la fuente;
- un JSON con los tiempos por etapa y por fragmento, el binario usado, el ctx y las
  banderas, de modo que un numero nunca queda sin la configuracion que lo produjo;
- el log del ``llama-server``, que la app manda a DEVNULL (``engine/server.py``) y
  que es justo donde el servidor dice que dispositivos vio, cuantas capas descargo,
  cuantos tokens tenia el prompt de verdad y si rechazo la peticion.

El texto del documento no se guarda en ningun caso: se guardan su tamano y su
recuento de tokens. La postura local-first no se rompe por instrumentar.

Ejemplos:

    uv run python tools/measure_run.py --doc ley.txt
    uv run python tools/measure_run.py --doc ley.txt --ctx 16384 \
        --server C:/ruta/llama-server.exe --flags "-fa on -ctk q8_0 -ctv q8_0"
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

from leyllana.config import load
from leyllana.engine import Progress, explain
from leyllana.engine.local import LocalProvider
from leyllana.types import Nivel


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="measure_run",
        description="Mide una corrida completa de explain() sobre un documento.",
    )
    p.add_argument("--doc", required=True, help="archivo de texto ya extraido")
    p.add_argument("--out", default="mediciones", help="carpeta de salida")
    p.add_argument("--label", default=None, help="nombre de la corrida")
    p.add_argument("--ctx", type=int, default=None, help="ctx del modelo local")
    p.add_argument(
        "--nivel",
        choices=[n.value for n in Nivel],
        default=Nivel.PUBLICO.value,
    )
    p.add_argument("--config", default=None, help="ruta a leyllana.toml")
    p.add_argument(
        "--server",
        default=None,
        help="binario llama-server a usar en vez del configurado",
    )
    p.add_argument(
        "--flags",
        default="",
        help=(
            "banderas extra para el llama-server, entre comillas "
            '(ej: "-fa on -ctk q8_0 -ctv q8_0")'
        ),
    )
    return p.parse_args()


def _instrumentar_servidor(banderas: list[str], log: Path) -> None:
    """Envuelve el ``Popen`` del modulo de servidor para no perder su log.

    ``LlamaServer.ensure`` arma el argv y manda stdout/stderr a DEVNULL, y no expone
    banderas extra. Envolver el ``Popen`` del modulo agrega las banderas y redirige
    la salida a un archivo sin duplicar la logica de arranque ni la espera de salud,
    y sobre todo sin cambiar el codigo de produccion para poder medirlo.
    """
    from leyllana.engine import server as srv

    popen_original = srv.subprocess.Popen
    fh = log.open("wb")

    def popen_instrumentado(args, **kwargs):
        kwargs["stdout"] = fh
        kwargs["stderr"] = fh
        return popen_original(list(args) + banderas, **kwargs)

    srv.subprocess.Popen = popen_instrumentado


def main() -> int:
    args = _parse_args()
    doc = Path(args.doc)
    salida = Path(args.out)
    salida.mkdir(parents=True, exist_ok=True)
    banderas = args.flags.split()
    nivel = Nivel(args.nivel)

    cfg = load(args.config)
    engine = cfg.engine
    if args.ctx is not None:
        engine = replace(
            engine, default_model=replace(engine.default_model, ctx=args.ctx)
        )
    if args.server is not None:
        engine = replace(engine, server_path=args.server)
    cfg = replace(cfg, engine=engine)

    etiqueta = args.label or f"ctx{engine.default_model.ctx}"
    log_servidor = salida / f"{etiqueta}-llama-server.log"
    _instrumentar_servidor(banderas, log_servidor)

    texto = doc.read_text(encoding="utf-8")
    print(f"=== {etiqueta} ===", flush=True)
    print(f"documento: {doc} ({len(texto)} caracteres)", flush=True)
    print(f"ctx: {engine.default_model.ctx}   nivel: {nivel}", flush=True)
    print(f"modelo: {engine.default_model.path}", flush=True)
    print(f"binario: {engine.server_path}", flush=True)
    print(f"gpu: {engine.gpu}   max_tokens: {engine.max_tokens}", flush=True)
    print(f"banderas extra: {' '.join(banderas) or '(ninguna)'}", flush=True)

    eventos: list[dict] = []
    inicio = time.monotonic()

    def anotar(p: Progress) -> None:
        t = time.monotonic() - inicio
        eventos.append(
            {
                "t": round(t, 2),
                "stage": str(p.stage),
                "fragmento": p.fragmento,
                "total": p.total,
                "detalle": p.detalle,
            }
        )
        print(f"[{t:8.1f}s] {p.texto()}", flush=True)

    # El arranque del servidor se mide aparte: es el costo de cargar el GGUF, que la
    # GUI paga una sola vez por sesion (ADR 0019), no el costo de la explicacion.
    provider = LocalProvider(cfg)
    t_srv = time.monotonic()
    provider._ensure_server()  # noqa: SLF001 - a proposito: separa carga de generacion
    arranque = time.monotonic() - t_srv
    print(f"arranque del llama-server: {arranque:.1f}s", flush=True)

    inicio = time.monotonic()
    error = None
    explicacion = None
    try:
        explicacion = explain(texto, nivel, cfg, progress=anotar, provider=provider)
    except BaseException as exc:  # noqa: BLE001 - se registra cualquier fallo
        error = f"{type(exc).__name__}: {exc}"
        print(f"FALLO: {error}", flush=True)
    total = time.monotonic() - inicio
    provider.close()

    # Duracion de cada fragmento: del aviso de uno al del siguiente. El ultimo no
    # tiene siguiente, asi que queda en None en vez de inventarle un final.
    avisos = [e for e in eventos if e["fragmento"] is not None]
    duraciones = []
    for actual, siguiente in zip(avisos, avisos[1:] + [None], strict=False):
        fin = siguiente["t"] if siguiente else None
        duraciones.append(
            {
                "fragmento": actual["fragmento"],
                "total": actual["total"],
                "inicio": actual["t"],
                "duracion": round(fin - actual["t"], 2) if fin is not None else None,
            }
        )

    registro = {
        "etiqueta": etiqueta,
        "documento": str(doc),
        "caracteres": len(texto),
        "ctx": engine.default_model.ctx,
        "nivel": str(nivel),
        "modelo": engine.default_model.path,
        "binario": engine.server_path,
        "gpu": engine.gpu,
        "max_tokens": engine.max_tokens,
        "threads": engine.threads,
        "banderas": banderas,
        "arranque_servidor_s": round(arranque, 2),
        "total_s": round(total, 2),
        "llamadas_map": len(avisos),
        "fragmentos_primer_nivel": avisos[0]["total"] if avisos else 1,
        "duraciones_fragmento": duraciones,
        "eventos": eventos,
        "log_servidor": str(log_servidor),
        "error": error,
    }
    (salida / f"{etiqueta}.json").write_text(
        json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if explicacion is not None:
        (salida / f"{etiqueta}.md").write_text(
            explicacion.to_markdown(), encoding="utf-8"
        )

    print(f"\ntotal: {total:.1f}s ({total / 60:.1f} min)", flush=True)
    print(
        f"llamadas del map: {len(avisos)} "
        f"(primer nivel: {registro['fragmentos_primer_nivel']} fragmentos)",
        flush=True,
    )
    medidas = [d["duracion"] for d in duraciones if d["duracion"] is not None]
    if medidas:
        print(
            f"por llamada: min {min(medidas):.1f}s  max {max(medidas):.1f}s  "
            f"media {sum(medidas) / len(medidas):.1f}s",
            flush=True,
        )
    print(f"registro: {salida / (etiqueta + '.json')}", flush=True)
    print(f"log del servidor: {log_servidor}", flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
