"""leyllana — decodificador de leyes y boletines chilenos en lenguaje llano.

Primer tool de Germen Digital Socialista (GDS). Local-first y soberano por
defecto: por defecto corre entero en la maquina del usuario y no se envia
ningun dato a la nube salvo opt-in explicito.

Los limites del sistema (cada uno testeable por separado) son:

- ``leyllana.input``  — resuelve una fuente (archivo/pegado/URL) a texto crudo.
- ``leyllana.prompt`` — arma el prompt en espanol con guardrail y disclaimer.
- ``leyllana.engine`` — ``explain(text, nivel)`` sobre un proveedor swappable.

La GUI (PySide6) se agrega en una fase posterior; ver ROADMAP.md.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
