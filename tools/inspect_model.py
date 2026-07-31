"""Lee el GGUF y calcula que ctx es viable, sin cargar el modelo.

Herramienta de desarrollo, no parte de la aplicacion. Solo lee el bloque de
metadatos del principio del archivo, asi que no toca RAM ni VRAM y responde al
instante. Contesta tres preguntas que conviene tener antes de medir nada:

- cual es el contexto nativo del modelo (el ctx de la config no es una propiedad
  del modelo, es una eleccion nuestra);
- cuanto pesa el KV cache por token, y por lo tanto cuanta memoria pide cada ctx,
  que es lo que decide si una tarjeta chica puede o no;
- en cuantos fragmentos queda un documento a cada ctx, calculado con el mismo
  chunking que corre en produccion (ADR 0017), porque el costo de una corrida es
  sobre todo el numero de llamadas.

Ejemplos:

    uv run python tools/inspect_model.py
    uv run python tools/inspect_model.py --doc ley.txt --model C:/ruta/modelo.gguf
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leyllana.config import load
from leyllana.engine.chunking import chars_for_tokens, estimate_tokens, split_structural
from leyllana.engine.model_fit import kv_bytes_per_token, read_gguf_metadata

# Reserva de tokens del system prompt en el engine (``_SYSTEM_RESERVE_TOKENS``).
_RESERVA_SISTEMA = 600

_CTX_CANDIDATOS = (4096, 8192, 12288, 16384, 24576, 32768, 49152, 65536)


def _escalar(valor):
    """Algunos modelos guardan estos campos como lista de una posicion."""
    return valor[0] if isinstance(valor, list) and valor else valor


def main() -> int:
    p = argparse.ArgumentParser(
        prog="inspect_model",
        description="Metadatos del GGUF, memoria del KV cache y fragmentos por ctx.",
    )
    p.add_argument("--model", default=None, help="GGUF a inspeccionar")
    p.add_argument("--doc", default=None, help="documento para la curva de fragmentos")
    p.add_argument("--config", default=None, help="ruta a leyllana.toml")
    args = p.parse_args()

    cfg = load(args.config).engine
    modelo = Path(args.model or cfg.default_model.path or "")
    if not modelo.is_file():
        print(f"no existe el modelo: {modelo}")
        return 2

    kv = read_gguf_metadata(modelo)
    arch = kv.get("general.architecture", "")
    pesos_gib = modelo.stat().st_size / 1024**3

    print(f"archivo:  {modelo.name}")
    print(f"pesos:    {pesos_gib:.2f} GiB")
    print(f"nombre:   {kv.get('general.name')}")
    print(f"arquitectura: {arch}")

    nativo = _escalar(kv.get(f"{arch}.context_length"))

    print(f"contexto nativo: {nativo}")
    print(f"ctx configurado: {cfg.default_model.ctx}")
    if nativo and cfg.default_model.ctx:
        print(f"  la config usa 1/{nativo // cfg.default_model.ctx} del nativo")

    bytes_por_token = kv_bytes_per_token(kv)
    if bytes_por_token is None:
        print("\nno se pudo calcular el KV cache: faltan metadatos de atencion")
        return 0

    # f16 es el tipo por defecto del KV en llama.cpp: 2 bytes por elemento, K y V
    # en cada capa. Con -ctk/-ctv q8_0 se reduce a la mitad.
    print(f"\nKV cache f16: {bytes_por_token / 1024:.1f} KiB por token")
    print(f"{'ctx':>7} {'KV f16':>9} {'KV q8_0':>9} {'+pesos f16':>11}")
    for ctx in _CTX_CANDIDATOS:
        f16 = bytes_por_token * ctx / 1024**3
        print(f"{ctx:>7} {f16:>8.2f}G {f16 / 2:>8.2f}G {f16 + pesos_gib:>10.2f}G")

    if not args.doc:
        return 0

    texto = Path(args.doc).read_text(encoding="utf-8")
    tokens = estimate_tokens(texto)
    print(f"\ndocumento: {len(texto)} caracteres, ~{tokens} tokens estimados")
    print(f"{'ctx':>7} {'presupuesto':>12} {'max_chars':>10} {'fragmentos':>11}")
    for ctx in _CTX_CANDIDATOS:
        presupuesto = ctx - cfg.max_tokens - _RESERVA_SISTEMA
        if presupuesto <= 0:
            continue
        if tokens <= presupuesto:
            fragmentos = 1
        else:
            fragmentos = len(
                split_structural(texto, max_chars=chars_for_tokens(presupuesto))
            )
        print(
            f"{ctx:>7} {presupuesto:>12} "
            f"{chars_for_tokens(presupuesto):>10} {fragmentos:>11}"
        )

    minimo = tokens + cfg.max_tokens + _RESERVA_SISTEMA
    print(f"\nuna sola pasada necesitaria ctx >= {minimo}")
    print(
        "Ojo: menos fragmentos no es automaticamente mejor. El numero de fragmentos "
        "de la primera vuelta no es el numero de llamadas: si los puntos clave "
        "reunidos tampoco caben, ADR 0017 reduce por niveles y las llamadas se "
        "multiplican. Y con una sola pasada el modelo pierde el medio del documento."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
