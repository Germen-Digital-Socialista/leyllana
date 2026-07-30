# tools — instrumentacion de desarrollo

Herramientas de medicion. **No son parte de la aplicacion**: no se empaquetan en la
rueda (`pyproject.toml` solo incluye `src/leyllana`), no las importa ningun modulo
de `src/`, y nada de lo que hacen cambia el comportamiento de leyllana.

Existen porque una corrida lenta o rara no se puede diagnosticar despues de que
termino. El 2026-07-29, para responder una sola pregunta del ROADMAP (subir `ctx` y
volver a medir), hubo que relanzar el binario a mano para averiguar cosas que la
aplicacion no registraba: que dispositivos ve el `llama-server`, cuantos tokens
tenia el prompt de verdad, y si el servidor rechazo la peticion. Esto es eso, hecho
una vez y guardado.

La aplicacion **si** registra ahora sus propias corridas: `leyllana.diagnostics`
escribe un JSON por corrida y guarda el log del `llama-server` en `mediciones/`
(`leyllana-gui --sin-diagnostico` lo apaga). Estas herramientas siguen siendo utiles
para lo que la ventana no hace: comparar builds, ctx y banderas sin abrir la GUI.

**Ninguna de estas herramientas guarda el texto del documento.** Guardan su tamano,
su recuento de tokens, los tiempos y la configuracion. La postura local-first no se
rompe por instrumentar.

## Las herramientas

| herramienta | que responde | costo |
|---|---|---|
| `inspect_model.py` | contexto nativo del modelo, memoria del KV cache por `ctx`, fragmentos por `ctx` | instantaneo, no carga el modelo |
| `fetch_norm.py` | baja una norma y la fija en disco para medir siempre los mismos bytes | un fetch |
| `measure_calls.py` | tokens/s de prompt y de generacion en un build, `ctx` y banderas dados; si el `ctx` cabe o muere | segundos a minutos |
| `measure_run.py` | una corrida completa de `explain()`: tiempo total, llamadas, tiempo por fragmento, y el log del servidor | minutos a horas |

Orden natural: `inspect_model` para descartar configuraciones inviables sin gastar
nada, `measure_calls` para comparar builds y banderas, y `measure_run` solo cuando
hace falta el numero de punta a punta.

## Uso

```sh
# Que ctx tiene sentido, y en cuantos fragmentos cae el documento
uv run python tools/inspect_model.py --doc mediciones/ley.txt

# Fijar el documento una vez
uv run python tools/fetch_norm.py \
    "https://www.bcn.cl/leychile/navegar?idNorma=1202434" mediciones/ley.txt

# Comparar una configuracion, sin esperar una corrida entera
uv run python tools/measure_calls.py --doc mediciones/ley.txt --ctx 16384 \
    --chars 51660 --server C:/ruta/llama-server.exe \
    --flags "-fa on -ctk q8_0 -ctv q8_0"

# La corrida completa
uv run python tools/measure_run.py --doc mediciones/ley.txt --ctx 16384 \
    --flags "-fa on -ctk q8_0 -ctv q8_0"
```

`--server` y `--flags` existen porque el `LlamaServer` de produccion fija su argv y
manda la salida del servidor a `DEVNULL` (`engine/server.py`). `measure_run.py`
envuelve el `Popen` de ese modulo para agregar banderas y quedarse con el log, en vez
de cambiar el codigo de produccion solo para poder medirlo. Si algun dia leyllana
expone esas banderas por config, esta envoltura se borra.

## Como leer los numeros

Tres cosas que no son obvias y que costaron una sesion entera aprender:

1. **El costo de una corrida es el numero de llamadas, no el tamano del documento.**
   Cada llamada del map genera hasta `max_tokens`, y la generacion es el gasto
   dominante. Subir `ctx` sirve porque reduce llamadas.
2. **El numero de fragmentos de la primera vuelta no es el numero de llamadas.** Si
   los puntos clave reunidos tampoco caben en el contexto, la reduccion jerarquica de
   ADR 0017 vuelve a correr. Medido: `ctx 4096` sobre una ley de 99.468 caracteres da
   13 fragmentos pero **25 llamadas** (13 -> 6 -> 3 -> 2), y `ctx 16384` da 3.
3. **Un build sin backend de GPU no avisa.** Corre en CPU y acepta `-ngl 999` sin
   queja. `measure_calls.py` imprime `--list-devices` primero justamente por eso: si
   la lista sale vacia, cualquier numero que siga es un numero de CPU.

Las mediciones hechas con estas herramientas estan en `ROADMAP.md`, con la
configuracion de cada una al lado del numero.
