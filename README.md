<div align="center">

<img src="assets/logo.svg" alt="leyllana" width="150">

# leyllana

**La ley, en lenguaje llano.**

[![Licencia: AGPL-3.0](https://img.shields.io/badge/licencia-AGPL--3.0-c1121f)](LICENSE)
[![Estado: acceso anticipado](https://img.shields.io/badge/estado-acceso%20anticipado-e76f00)](ROADMAP.md)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)](PRD.md)
[![Local-first: sin conexión](https://img.shields.io/badge/local--first-sin%20conexi%C3%B3n-2a9d8f)](docs/adr/0005-local-first-data-sovereignty.md)
[![Hecho en Chile](https://img.shields.io/badge/hecho%20en-Chile-004b87)](#germen-digital-socialista)

</div>

> Aplicación de escritorio, local y gratuita, que explica leyes y proyectos de ley chilenos en lenguaje claro. Cargas una ley o un boletín, y te dice qué hace, a quién afecta y cuáles son sus artículos clave, en español simple. Corre en tu propio computador: por defecto, ningún dato sale de tu máquina.

## Por qué existe

La ley es pública, pero no se entiende. Un boletín del Congreso puede tener veinte páginas que remiten a otras diez que modifican una tercera, y para cuando llegas al artículo que te importa ya no sabes si habla de ti. Eso no le pasa solo al vecino. Le pasa al trabajador que firma sin leer, a la dirigenta que tiene que explicarle a su gente algo que ella misma apenas descifró, y a más de un parlamentario que vota una norma que no alcanzó a digerir.

Esa distancia entre el texto y la persona no es un accidente. Es una barrera, y las barreras siempre las paga el mismo lado.

leyllana es la primera herramienta del **Germen Digital Socialista**. Hace una cosa y la hace bien: agarra el texto de una ley y lo devuelve en lenguaje llano, ordenado, sin inventar nada. No es un abogado en una caja. Es una linterna para leer lo que ya es tuyo.

## Qué hace

Le das una ley o un boletín, y te devuelve una explicación estructurada en español:

- **Qué hace** la norma.
- **A quién afecta.**
- **Artículos clave**, traducidos a lenguaje humano.
- **En una frase**, el resumen que puedes repetir de memoria.

Con un control de **nivel**: `publico` para cualquier persona, `tecnico` para quien trabaja en el Congreso o asesora. Cambia el tono y la profundidad, nunca los hechos.

La entrada llega como tú la tengas: un archivo (`.txt` o `.pdf`), texto pegado, o el enlace directo a una fuente oficial (BCN, Senado, Cámara).

## Cómo funciona, y por qué corre en tu máquina

Por defecto, leyllana usa un modelo de lenguaje **local**, en tu propio computador, sin conexión. La misma decisión que tomamos en MuniGPT: los datos no se van a una nube ajena. Entender la ley no debería depender de un servidor en otro país ni de una suscripción.

Si quieres más potencia, hay nube, y no necesitas pagar una *API* para usarla. Si ya tienes una suscripción a Claude o a Kimi, leyllana maneja el CLI de esa suscripción por ti y aprovecha lo que ya estás pagando. Cualquier otro agente de terminal se enchufa con una línea de configuración, sin código nuevo.

Eso sí, nada sale de tu computador en silencio. Cada envío a la nube hay que autorizarlo en ese mismo comando, con `--acepto-nube`. ¿Se te olvidó el *flag*? No se manda nada, y te lo dice. Las claves de *API* vienen más adelante; hoy no te hacen falta.

Dos reglas que no se transan:

1. **No inventa.** El modelo solo resume lo que está en el texto que le diste. Si el texto no alcanza para responder algo, lo dice, no lo rellena.
2. **No es asesoría legal.** Cada explicación lo lleva escrito. leyllana te ayuda a entender; para una decisión legal, habla con un abogado.

## Cómo se usa hoy

Todavía no hay ventana, así que por ahora se trabaja desde la terminal:

```bash
# instala, con el extra que hace falta para leer PDF
uv sync --extra pdf

# copia la configuración de ejemplo y apúntala a tu modelo local
cp leyllana.example.toml leyllana.toml

# una norma desde el sitio oficial de la BCN
uv run leyllana --url "https://www.bcn.cl/leychile/navegar?idNorma=1194515" --nivel publico

# un PDF que tengas guardado, en registro técnico
uv run leyllana --file proyecto.pdf --nivel tecnico

# con tu suscripción en la nube, autorizando el envío
uv run leyllana --file proyecto.pdf --acepto-nube
```

`leyllana.example.toml` viene comentado línea por línea: qué modelo local usar, o qué CLI de suscripción manejar.

## Estado

Acceso anticipado, pero ya no es solo diseño. El motor funciona de principio a fin: le das una ley, eliges el nivel, y salen las cuatro secciones con su fuente identificada arriba. Está probado contra normas reales de la BCN, tanto con el modelo local como con la nube por suscripción.

Lo que falta es la cara. La interfaz gráfica es la fase 3, y el instalador para quien no quiere saber nada de terminales es la 4.

El diseño completo sigue publicado y al día: la visión (`PRD.md`), la hoja de ruta (`ROADMAP.md`) y las decisiones de arquitectura (`docs/adr/`), una por cada cosa que se decidió y por qué se decidió así. Si quieres aportar, empieza por ahí.

## Germen Digital Socialista

Software público, gratis, hecho desde la izquierda para que la tecnología no sea una muralla más. leyllana es la semilla. Por eso el nombre: un germen es lo que brota. La idea es simple y es vieja, y sigue siendo la buena: las herramientas del pueblo, en manos del pueblo.

## Licencia

[AGPL-3.0](LICENSE). Copyleft fuerte, y con la cláusula que cierra la puerta a que alguien tome esto, lo cambie, lo monte como servicio y se lo quede. Lo que nace libre, se queda libre.

---

<sub>**Palabras clave:** leyllana, Germen Digital Socialista, lenguaje claro, lenguaje llano, leyes chilenas, boletines, proyectos de ley, legislación, Chile, legaltech, civic tech, gov tech, inteligencia artificial, IA, LLM, local-first, offline, llama.cpp, PySide6, código abierto, AGPL, español.</sub>
