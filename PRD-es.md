# PRD — leyllana (versión en español)

**Producto:** leyllana
**Organización:** Germen Digital Socialista (GDS)
**Estado:** Borrador (previo a la implementación)
**Responsable:** Felipe Carvajal Brown
**Idioma:** Este documento está en español. La versión de referencia es `PRD.md`
(en inglés); ante cualquier diferencia, prima esa.

---

## 1. Visión

La ley chilena es pública, pero no es legible. Las normas y los boletines
(proyectos de ley) están escritos en un registro difícil de leer incluso para
abogados, y muchas veces opaco para los legisladores que los votan y para la
ciudadanía que obligan. leyllana convierte el texto de una ley o un boletín en
una explicación estructurada, en español simple: un "decodificador de leyes",
para que entender una norma no exija un título de Derecho ni pagar por asesoría.

leyllana es la primera herramienta del Germen Digital Socialista. Está construida
con enfoque local: por defecto corre completamente en la máquina de quien la usa,
y ningún dato sale de ahí salvo que la persona elija explícitamente un proveedor
en la nube. Es a la vez una propiedad de privacidad y una posición política: la
comprensión pública de la ley no debería depender de una nube extranjera ni de
una suscripción.

## 2. Problema

- El texto legal y legislativo es denso, autorreferente y lleno de remisiones
  cruzadas; un solo artículo puede ser ilegible sin los diez que modifica.
- Las personas más afectadas por una ley (trabajadores, arrendatarios, pequeños
  operadores) son las que menos herramientas tienen para leerla.
- Incluso legisladores y asesores no alcanzan a digerir a fondo cada boletín que
  manejan.
- Los resumidores existentes son solo nube, priorizan el inglés y no dan garantía
  de que no estén inventando números de artículo u obligaciones.

## 3. Objetivos y no-objetivos

### Objetivos (lo que la v1 debe lograr)
- Tomar una ley o boletín chileno como entrada y producir una explicación
  estructurada y clara en español.
- Correr totalmente sin conexión por defecto (motor local `llama.cpp`).
- No fabricar nunca contenido legal: la explicación se apoya estrictamente en el
  texto entregado.
- Ser usable por una persona no técnica a través de una interfaz gráfica.
- Ofrecer dos niveles de audiencia: `publico` (público general) y `tecnico`
  (legislador / asesor).

### No-objetivos (fuera de alcance en la v1)
- Asesoría o interpretación legal de ningún tipo (la herramienta es una ayuda, no
  asesoría legal).
- Un servicio web alojado o un backend multiusuario.
- Comparación / diferencias entre leyes, preguntas y respuestas libres sobre un
  corpus, o seguimiento legislativo: son candidatas a futuras herramientas del
  GDS, no parte de la v1 de leyllana.
- Cualquier función que exija, por defecto, que los datos salgan de la máquina.

## 4. Usuarios

- **Público general** — quiere saber, en una pantalla, qué hace una ley y si le
  afecta.
- **Legisladores y asesores** — quieren un resumen fiel, en registro técnico, de
  un boletín, rápido y con los artículos clave a la vista.
- **Prensa / sociedad civil** — quieren una lectura defendible en lenguaje claro
  que puedan citar y contrastar con la fuente.

## 5. Requisitos funcionales

- **RF-1 Entrada, de tres formas.** Aceptar entrada como (a) un archivo local:
  `.txt` leído directo, `.pdf` extraído con PyMuPDF; (b) texto pegado; (c) una URL
  de fuente oficial (endpoint de exportación de BCN / leychile.cl, boletín del
  Senado / la Cámara).
- **RF-1.1 Validación de documentos y respaldo con OCR.** Detectar archivos
  vacíos, protegidos o escaneados y extracciones de texto incompletas, y advertir
  a la persona antes de generar una explicación. Cuando un `.pdf` está escaneado o
  es solo imagen (sin capa de texto usable), recurrir a OCR: Tesseract vía
  `pytesseract` (`-l spa`), rasterizando las páginas con pdf2image/Poppler; ningún
  modelo de visión corre en el camino por defecto (el mismo stack y la misma
  postura de "transcribir, no alucinar" del pipeline OCR de `chilecompracl`).
  **El OCR se usa solo cuando es necesario** — únicamente como respaldo cuando la
  extracción de texto falla, nunca sobre documentos que ya entregan una capa de
  texto usable. **El OCR puede fallar o degradarse** — malas lecturas de escaneos
  (p. ej. "artículo 12" leído como "artículo 72"), errores de transcripción o
  binarios de sistema ausentes (Tesseract/Poppler); la herramienta marca la
  extracción como fallida o de baja confianza en vez de pasarle texto malo al
  modelo en silencio. Advertencia de fidelidad: la explicación es tan fiel como el
  texto extraído. Ver ADR 0011.
- **RF-2 Salida estructurada.** Producir secciones fijas en español: **Qué
  hace**, **A quién afecta**, **Artículos clave**, **En una frase**.
- **RF-3 Nivel de audiencia.** Un control `nivel` con dos valores, `publico` y
  `tecnico`, que cambia registro y profundidad, no los hechos.
- **RF-4 Motor intercambiable.** Una única interfaz `explain(text, nivel)`
  respaldada por un proveedor configurable (ver ADR 0003). El proveedor por
  defecto es `llama.cpp` local.
- **RF-5 Nube opcional.** Proveedores opcionales: Claude, OpenAI/Codex, Gemini,
  vía clave de API o vía sus CLIs de suscripción web ejecutados en el panel de
  terminal incorporado (ver ADR 0004).
- **RF-5.1 Consentimiento para servicios externos.** Antes de enviar cualquier
  contenido a un proveedor en la nube, la aplicación informa con claridad que el
  documento saldrá del equipo y solicita confirmación explícita — el enfoque local
  y la privacidad son parte central del proyecto (ADR 0004, 0005).
- **RF-6 Barrera anti-invención.** El prompt del motor prohíbe inventar
  artículos, números, citas u obligaciones; la salida se apoya solo en el texto
  de entrada. Si el texto no alcanza, la herramienta lo dice en vez de adivinar.
- **RF-6.1 Trazabilidad.** Cada artículo, cifra, fecha u obligación mencionada en
  la explicación debe usar la redacción tal como aparece en el texto de origen
  (verbatim, garantizado por la barrera anti-invención), de modo que quien lee
  pueda contrastar cada dato con la entrada. El enlace clicable de cada mención a
  su fragmento de origen queda postergado (ver ROADMAP).
- **RF-7 Descargo.** Cada explicación lleva un pie visible que indica que es una
  ayuda y no asesoría legal.
- **RF-7.1 Identificación de la fuente.** La salida muestra, cuando estén
  disponibles, el título del documento, el tipo de norma, el organismo de origen,
  la fecha, la versión analizada, la URL y la fecha de consulta. Se muestran solo
  cuando se pueden extraer y nunca se inventan (misma regla que RF-6).
- **RF-8 Exportar.** Guardar la explicación como Markdown.
- **RF-9 Terminal incorporada.** Un panel de terminal junto a la interfaz
  principal (pywinpty en Windows) para operar los CLIs de los proveedores.
- **RF-10 Estado del procesamiento.** Durante la extracción y el análisis, la
  interfaz muestra que el sistema sigue activo: una barra de progreso o indicador
  animado, la etapa actual (**cargando**, **extrayendo texto**, **analizando**,
  **verificando**, **generando resultado**) y el tiempo transcurrido. Cuando sea
  técnicamente posible, muestra el porcentaje completado o el número de fragmentos
  procesados. La persona usuaria puede cancelar la operación. (Fase GUI — ver
  ROADMAP Fase 3.)

## 6. Requisitos no funcionales

- **Local-first / soberano:** el camino por defecto no hace llamadas de red. Las
  llamadas a la nube ocurren solo con opt-in explícito.
- **Fidelidad antes que fluidez:** un correcto "no se puede determinar con este
  texto" vale más que una fabricación fluida.
- **Español en todo** el UI y la salida.
- **Compatible con CPU:** el funcionamiento local básico no requiere GPU (no se
  supone GPU). Cuando exista una GPU compatible, podrá usarse opcionalmente para
  mejorar el rendimiento. La CPU sigue siendo la línea base, igual que MuniGPT.
  Ver ADR 0012.
- **Base de código en un solo lenguaje** (Python) para mantenibilidad.
- **Accesibilidad visual (fase GUI):** la interfaz admite modo claro y oscuro,
  tipografía redimensionable y contraste adecuado para la lectura prolongada de
  documentos legales.

## 7. Arquitectura (alto nivel)

```
            ┌──────────────────────── App de escritorio PySide6 ────────────────────────┐
            │                                                                            │
  fuente ──▶│  capa entrada           capa motor             capa salida    terminal    │
 (archivo/  │  resolver + extraer ──▶  explain(text,nivel) ──▶ secciones   │  panel      │
  pegar/    │  (txt/pdf/url)           proveedor              en español   │ (pywinpty:  │
  url)      │                          intercambiable        + descargo   │  claude/    │
            │                          · llama.cpp local*      + exportar  │  codex/     │
            │                          · claude / codex /                  │  gemini CLI)│
            │                            gemini (api o CLI)                │             │
            └────────────────────────────────────────────────────────────────────────┘
                                        * por defecto
```

Límites de componentes (cada uno testeable por separado):
- **entrada** — resuelve una fuente a texto crudo: valida el documento y, para
  PDFs escaneados solo cuando hace falta, le aplica OCR (ADR 0011). No sabe nada
  del motor.
- **motor** — `explain(text, nivel) -> resultado estructurado`. No sabe nada de
  la interfaz. El proveedor se elige por configuración.
- **prompt** — arma el prompt en español con las barreras y el control `nivel`.
  Puro, sin E/S.
- **gui** — la app PySide6: panel de fuente, panel de resultado, terminal
  incorporada.

## 8. Criterios de éxito

- Una persona no técnica puede cargar un boletín real y obtener una explicación
  fiel en cuatro secciones, en español, sin tocar un archivo de configuración.
- Con la red deshabilitada, el camino por defecto (local) igual funciona de punta
  a punta.
- En una verificación contra la fuente, la salida no inventa nada: cada artículo
  o cifra que nombra está presente en la entrada.

## 9. Preguntas abiertas

- Qué modelo local liviano exacto se distribuye por defecto (clase Qwen) y el de
  respaldo para poca RAM, siguiendo la selección por configuración de MuniGPT.
- Detalles de la terminal en plataformas distintas de Windows (pywinpty es
  específico de Windows; un backend basado en ptyprocess sería el camino
  Linux/macOS).
- Objetivo de empaquetado/instalador para la v1 (postergado a la hoja de ruta).
- Empaquetar los binarios de sistema del OCR (Tesseract + Poppler) en el
  instalador de la v1 para una persona no técnica (Fase 4), ya que no son
  dependencias pip.

## 10. Referencias

- Decisiones: `docs/adr/` (ver el índice en `docs/adr/README.md`).
- Proyecto hermano reutilizado por sus patrones: MuniGPT (llama.cpp local,
  extracción de PDF, descarga desde BCN).
