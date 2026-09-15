# Atlas: uso responsable de Nebius Token Factory

El proyecto usa créditos limitados de Nebius Token Factory. Respeta estas
reglas en cualquier cambio o prueba:

- Nunca leas, imprimas, pegues ni subas `NEBIUS_API_KEY`; sólo puede vivir en
  `.env` local o en el gestor de secretos del despliegue.
- No hagas llamadas externas al modelo salvo que sean necesarias para la tarea
  actual. Para comprobar conectividad usa únicamente `python -m core.llm`:
  ejecuta una llamada a Nemotron Nano con salida de cuatro tokens como máximo.
- No uses Nemotron Ultra para pruebas de conectividad, depuración o ejemplos.
  Antes de una prueba con Ultra, ingesta, evaluación por lote, fine-tuning,
  sandbox o despliegue que consuma Nebius, explica el propósito, estima el
  consumo y pide confirmación explícita.
- Por defecto usa mocks, fixtures y tests locales. Las pruebas de integración
  con Token Factory deben ser pequeñas, puntuales y reportar los tokens
  consumidos, sin registrar prompts sensibles.
- Mantén todas las llamadas a Token Factory en `core/llm.py`; no dupliques la
  URL de la API ni crees clientes directos en otros módulos.
