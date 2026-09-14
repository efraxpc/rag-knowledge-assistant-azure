# LangGraph: flujo explicado en ocho hojas A4

[PDF de ocho hojas](langgraph-a4.pdf) · [Versión para navegador](index.html) ·
[Guía del flujo](../../langgraph-flow.md) ·
[Diagrama original completo](../../langgraph-flujo-explicado.mmd)

Estas láminas dividen el flujo de preguntas en partes para poder leerlo e
imprimirlo. Conservan los ocho nodos reales de LangGraph, las decisiones de
Python y las llamadas a Entra ID, Azure AI Search y Azure OpenAI. El diagrama
original y las láminas técnicas anteriores se mantienen.

Imprime el PDF en **A4 horizontal, al 100 %, una página por hoja**. Si imprimes
desde el navegador, selecciona A4 horizontal y desactiva los encabezados y pies
del navegador. Las flechas hacia otra hoja indican dónde continuar la lectura.

| Hoja | Qué explica | SVG | Fuente Mermaid |
| --- | --- | --- | --- |
| 1 | Mapa de los ocho nodos y referencias a las otras hojas. | [Lámina](hojas/01-vision-general.svg) | [Fuente](hojas/01-vision-general.mmd) |
| 2 | Token de la API, validación JWT, OBO Search y preparación diferida de OpenAI. | [Lámina](hojas/02-entrada-identidad.svg) | [Fuente](hojas/02-entrada-identidad.mmd) |
| 3 | Búsqueda textual, filtros, duplicados y única consulta alternativa local. | [Lámina](hojas/03-busqueda-alternativa.svg) | [Fuente](hojas/03-busqueda-alternativa.mmd) |
| 4 | Copias del contexto, presupuesto de caracteres, pregunta original y estado. | [Lámina](hojas/04-preparar-contexto.svg) | [Fuente](hojas/04-preparar-contexto.mmd) |
| 5 | OBO Cognitive Services, rol OpenAI, chat completions y reutilización del cliente. | [Lámina](hojas/05-generacion-azure.svg) | [Fuente](hojas/05-generacion-azure.mmd) |
| 6 | Reglas locales de citas, control desactivable y reparación limitada. | [Lámina](hojas/06-citas-reparacion.svg) | [Fuente](hojas/06-citas-reparacion.mmd) |
| 7 | Respuesta, dos abstenciones, cierre de recursos y errores HTTP. | [Lámina](hojas/07-salida-errores.svg) | [Fuente](hojas/07-salida-errores.mmd) |
| 8 | Variables, rangos, trazas, evaluación CLI, juez offline y demostración. | [Lámina](hojas/08-configuracion-trazas.svg) | [Fuente](hojas/08-configuracion-trazas.mmd) |

## Cómo seguir las flechas

Los **rectángulos numerados** corresponden a funciones reales:
`search`, `rewrite_query`, `prepare_context`, `generate`, `validate_citations`,
`repair`, `abstain` y `finish`. Los **rombos** son condiciones implementadas en
Python; no son agentes ni pasos ejecutados por un modelo. Otros rectángulos
representan entrada, recursos Azure, datos o notas.

Las flechas continuas indican orden de ejecución; las punteadas indican llamadas
o dependencias. La hoja 1 resume las condiciones en sus etiquetas para mantener
el mapa compacto. Las hojas 3 y 6 muestran los rombos correspondientes.

Los valores predeterminados permiten **dos búsquedas y dos generaciones en
total**: la segunda búsqueda solo ocurre si la primera está vacía y existe una
consulta simplificada diferente. La segunda generación es una reparación por
citas inválidas. El grafo no reintenta errores HTTP ni cambia la identidad del
usuario para acceder a Azure.

Una respuesta con citas localizables no demuestra que cada afirmación tenga
respaldo factual. El juez evalúa las respuestas offline y no participa en la
petición de usuario. La falta de contexto y las citas inválidas agotadas producen
abstenciones normales HTTP 200, mientras que los errores externos se propagan
como errores controlados.

## Probar las ramas sin Azure

```bash
python -m app.commands.demo_answer_graph --scenario all
```

La demo muestra `success`, `recovered`, `empty`, `repair`, `invalid` y
`provider-error`. Usa dobles en memoria y opciones predeterminadas; no llama a la
API HTTP ni a Azure y no lee `.env`. `demo_calls` permite comparar las llamadas
con las trazas de cada nodo.

## Fuentes y edición

Las hojas describen el código revisado el **13 de septiembre de 2026**:

- [Nodos, estado y decisiones](../../../app/services/answer_graph.py).
- [Entrada del servicio y ciclo de vida del cliente](../../../app/services/answer.py).
- [JWT](../../../app/core/auth.py) y [dependencias FastAPI](../../../app/api/dependencies.py).
- [OBO y recursos](../../../app/core/resources.py).
- [Búsqueda textual](../../../app/integrations/azure_text_search.py) y
  [chat completions](../../../app/integrations/azure_openai_chat.py).
- [Settings](../../../app/core/config.py) y [demostración](../../../app/commands/demo_answer_graph.py).
- [Evaluación offline](../../llm-as-a-judge.md).

Edita las fuentes `.mmd` para cambiar nodos o conexiones. El archivo
[pages.json](pages.json) mantiene el orden, los títulos y las continuaciones de
las ocho hojas, además de las notas que se imprimen bajo cada dibujo. La
distribución final puede variar entre visores Mermaid;
para imprimir utiliza el PDF o los SVG preparados para estas láminas.

Para regenerar el HTML, los SVG y el PDF, necesitas Mermaid CLI (`mmdc`),
Chromium y los paquetes Python `playwright` y `pypdf`. Desde la raíz del
repositorio ejecuta:

```bash
python3 docs/diagrams/langgraph-a4/generate.py
```

Si Chromium está en otra ubicación, indica su ejecutable con `--browser`.
El generador verifica que haya ocho páginas A4 horizontales y que el texto de
los diagramas alcance al menos 10 puntos al ajustarlo a cada hoja.
