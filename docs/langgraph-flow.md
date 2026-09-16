# Flujo RAG con LangGraph

El servicio de respuestas organiza sus pasos con un grafo explícito: recuperar
texto, decidir si alcanza, generar y comprobar las citas. Las decisiones siguen
reglas locales y límites configurados. El modelo generador no elige herramientas
ni decide cuántas veces se ejecuta el flujo.

El [diagrama Mermaid](langgraph-flow.mmd) permite estudiar cada decisión. Esta
guía complementa los diagramas anteriores: el PDF técnico de diez hojas y la
visión global se conservan como las láminas de la versión anterior del flujo.

El [flujo explicado paso a paso](langgraph-flujo-explicado.mmd) muestra los ocho
nodos reales, sus decisiones, las llamadas Azure y el cierre de recursos. Las
flechas continuas indican el orden; las punteadas muestran interacciones o
dependencias. Los rombos representan condiciones, no nodos adicionales.

Para imprimirlo por partes, utiliza el [PDF de ocho hojas A4 horizontales](diagrams/langgraph-a4/langgraph-a4.pdf).
El [índice de las hojas](diagrams/langgraph-a4/README.md) incluye las fuentes
Mermaid y las versiones SVG; cada hoja indica dónde continúa el recorrido.

## Recorrido de una pregunta

1. **Buscar.** Para preguntas concretas, una función local elimina puntuación y
   palabras de relleno en español e inglés antes de consultar Azure AI Search.
   Las solicitudes globales, como resumir un documento, recuperan directamente
   sus fragmentos con `search_text="*"`. La recuperación sigue siendo textual:
   no se calculan embeddings.
2. **Comprobar si hay fragmentos.** Si la búsqueda por términos no devuelve
   resultados y hay un `document_id`, el segundo intento recupera hasta 20 chunks
   del documento seleccionado. El wildcard nunca se ejecuta sin filtro de
   documento, por lo que no mezcla archivos. La generación recibe siempre la
   pregunta original y el contexto continúa limitado por su presupuesto.
3. **Abstenerse si sigue vacío.** Si no hay una consulta diferente que probar o
   se agotaron las búsquedas sin contexto, devuelve el aviso de información
   insuficiente y `context=[]`. No obtiene un token OpenAI ni llama al modelo.
4. **Preparar contexto.** Los fragmentos disponibles se ajustan a un presupuesto
   de 12.000 caracteres por defecto. El ajuste crea copias, sin modificar los
   fragmentos originales. Las fuentes y páginas acompañan al texto que se
   entrega al generador; `context` devuelve únicamente los fragmentos preparados
   que recibió el modelo. El límite se mide en caracteres, no en tokens.
   Cuenta el contenido de los fragmentos; no incluye la pregunta, las fuentes,
   el envoltorio JSON ni las instrucciones del prompt.
5. **Generar.** Azure OpenAI recibe la pregunta y el contexto preparado. Solo al
   llegar aquí la API necesita la credencial delegada de OpenAI.
6. **Validar citas.** Una comprobación local compara las referencias de la
   respuesta con las fuentes y páginas del contexto. No usa otro modelo.
7. **Reparar dentro del límite.** Si las citas fallan y queda presupuesto de
   generación, se vuelve a llamar al generador con instrucciones para
   corregirlas. Por defecto hay dos llamadas de generación en total: la inicial
   y una reparación.
8. **Responder o abstenerse.** Si la comprobación pasa, devuelve `answer` y
   `context`. Si las citas siguen siendo inválidas tras agotar el presupuesto,
   devuelve una abstención y conserva el contexto disponible para revisión.

Un fallo del proveedor interrumpe la petición con el error controlado
correspondiente. El grafo no implementa reintentos de errores HTTP ni de
autenticación: la segunda búsqueda se debe a contexto vacío y la reparación a
citas inválidas. Los límites cuentan llamadas desde el grafo; no sustituyen las
políticas internas de transporte de un SDK.

La búsqueda descarta fragmentos duplicados por `(document_id, id)` y fragmentos
de otro documento cuando se solicitó uno concreto. Este filtrado también se
aplica a la búsqueda simplificada. El filtro de documento no sustituye Entra ID
o RBAC ni constituye una comprobación de propiedad del archivo.

## Qué comprueba la validación local

Debe existir al menos una cita. Cada cita debe referenciar una fuente incluida
en el contexto y, para un fragmento con página, una página disponible para esa
fuente. Los formatos esperados son `[manual.pdf, p. 2]` y `[manual.md]`.
Una cita que contiene solo la fuente se acepta únicamente si el contexto
contiene un fragmento de esa fuente con `page=None`. Una referencia a otra
fuente o página no queda respaldada por ese contexto.
La fuente se compara con su nombre exacto. Los textos entre corchetes se tratan
como referencias; por ejemplo, `[nota]` fallaría si no es una fuente permitida.
También se rechazan respuestas vacías o de más de 16.000 caracteres.

La comprobación permite detectar referencias ausentes o incompatibles con los
fragmentos. **No demuestra que todas las afirmaciones de la respuesta sean
verdaderas o estén respaldadas por el contenido citado.** Tampoco comprueba la
cobertura de cada afirmación. Una cita válida puede acompañar a una afirmación
incorrecta; el juez offline evalúa también ese aspecto.

## Cómo leer el código y las trazas

La entrada común es [AnswerService](../app/services/answer.py). Abre el cliente
generador únicamente cuando hace falta y lo cierra al terminar, también si hay
un error. [AnswerGraph](../app/services/answer_graph.py) define estos nodos:

| Nodo en el código y el log | Trabajo |
| --- | --- |
| `search` | Recuperar y filtrar los fragmentos. |
| `rewrite_query` | Preparar el fallback acotado al documento seleccionado. |
| `prepare_context` | Copiar y ajustar el contenido al presupuesto. |
| `generate` | Pedir un borrador al generador. |
| `validate_citations` | Aplicar las reglas locales o aceptar el borrador si están desactivadas. |
| `repair` | Preparar las instrucciones para otra generación. |
| `abstain` | Elegir el aviso de contexto vacío o de citas inválidas. |
| `finish` | Construir la respuesta final. |

El estado separa la pregunta original de la consulta de búsqueda e incluye
contexto, prompt, borrador, resultado de validación y contadores. Puede contener
texto privado durante la ejecución. Los clientes y credenciales quedan fuera
del estado; no se configura persistencia ni se comparte una sesión entre
preguntas. Las trazas de nodos registran únicamente los campos operativos
descritos más abajo.

## Límites y configuración

Los valores se leen mediante `Settings`, igual que el resto de las variables
`APP_*`. En local se colocan en `.env` o en el environment del proceso; para una
API publicada se configuran en el environment de Container Apps. Las variables
del runner de CI se configuran por separado y no se copian al contenedor.

```dotenv
APP_RAG_MAX_SEARCH_ATTEMPTS=2
APP_RAG_MAX_GENERATION_ATTEMPTS=2
APP_RAG_MAX_CONTEXT_CHARACTERS=12000
APP_RAG_VERIFY_CITATIONS=true
APP_RAG_TRACE_ENABLED=true
```

| Variable | Valor por defecto | Controla |
| --- | --- | --- |
| `APP_RAG_MAX_SEARCH_ATTEMPTS` | `2` | Total máximo de búsquedas por pregunta; configurable entre 1 y 2. |
| `APP_RAG_MAX_GENERATION_ATTEMPTS` | `2` | Total máximo de llamadas al generador, incluidas las reparaciones; configurable entre 1 y 3. |
| `APP_RAG_MAX_CONTEXT_CHARACTERS` | `12000` | Presupuesto del contenido de los fragmentos; configurable entre 1 y 60.000 caracteres. |
| `APP_RAG_VERIFY_CITATIONS` | `true` | Comprobación local de las citas y decisión de reparar o abstenerse. |
| `APP_RAG_TRACE_ENABLED` | `true` | Registro de las etapas del grafo. |

Una sola generación como máximo impide la reparación. Desactivar la
comprobación de citas elimina ese control local. Los límites no aseguran un
tiempo total ni equivalen a un presupuesto de tokens: cada llamada generadora
permite hasta 8.000 tokens de completion y usa razonamiento `minimal` por defecto.
Con la configuración predeterminada, una reparación puede consumir una segunda
llamada con esos mismos límites, además de los tokens de entrada de cada llamada.

## Entra ID y obtención diferida del token OpenAI

En las peticiones HTTP, FastAPI conserva la validación JWT y el flujo
On-Behalf-Of con la identidad del usuario. Search utiliza su token delegado para
recuperar los fragmentos. El token de Cognitive Services se obtiene de forma
diferida, cuando el grafo llega a la generación.

Los scopes siguen siendo `https://search.azure.com/.default` para Search y
`https://cognitiveservices.azure.com/.default` para Azure OpenAI.

Así, una pregunta que sigue sin contexto después de las búsquedas termina sin
intercambiar un token OpenAI. Esto no reemplaza los permisos de Entra o RBAC:
cuando sí hace falta generar, el usuario sigue necesitando el consentimiento
delegado y el rol de Azure OpenAI. No hay alternativa con `az login` ni con la
identidad administrada de Container Apps si falla la autenticación del usuario.

## Ver las etapas sin Azure

La demostración usa almacenes y generadores simulados en memoria. No requiere
credenciales, índices ni recursos de Azure, y muestra las etapas y el resultado.
Usa las opciones predeterminadas de `AnswerService`: no lee `Settings` ni `.env`.

```bash
python -m app.commands.demo_answer_graph --scenario success
python -m app.commands.demo_answer_graph --scenario recovered
python -m app.commands.demo_answer_graph --scenario empty
python -m app.commands.demo_answer_graph --scenario repair
python -m app.commands.demo_answer_graph --scenario invalid
python -m app.commands.demo_answer_graph --scenario provider-error
```

Para recorrer todos los escenarios:

```bash
python -m app.commands.demo_answer_graph --scenario all
```

| Escenario | Qué permite observar | Búsquedas / generaciones |
| --- | --- | --- |
| `success` | Recuperación con contexto y respuesta con citas válidas. | `1 / 1` |
| `recovered` | La primera búsqueda está vacía; la consulta simplificada encuentra contexto y se genera una respuesta. | `2 / 1` |
| `empty` | Búsqueda vacía, simplificación local, nueva búsqueda y abstención sin generación. | `2 / 0` |
| `repair` | Una primera respuesta con citas inválidas y una reparación correcta. | `1 / 2` |
| `invalid` | Las citas siguen siendo inválidas y se devuelve una abstención con contexto. | `1 / 2` |
| `provider-error` | El proveedor simulado falla y el flujo termina con un error controlado. | `1 / 1` |

El campo `demo_calls` muestra las llamadas hechas a cada doble. Permite comparar
ese conteo con los nodos y decisiones de las trazas. En `provider-error`, la demo
imprime el error simulado como resultado y puede continuar con los otros casos.

Estos casos demuestran las transiciones y límites. No miden la calidad de Azure
Search o del modelo desplegado, ni ejecutan el juez offline.

## Trazas de ejecución

Con `APP_RAG_TRACE_ENABLED=true`, cada nodo registra una traza a nivel `INFO` en
`uvicorn.error`. Se puede seguir una ejecución mediante su `request_id`; las
trazas incluyen etapa, contadores, resultado de la decisión y duración en
milisegundos.

Los registros de nodos no incluyen la pregunta, los fragmentos, la respuesta,
los prompts ni los tokens de autenticación. Los datos de decisión y duración
permiten comprobar, por ejemplo, si una consulta hizo una o dos búsquedas o si
necesitó reparar las citas. Para observar el flujo real, usa la terminal de
Uvicorn o de `./scripts/run_local.sh`.

## Relación con CI y el juez

La API y `generate_evaluation_answers` utilizan el mismo `AnswerService` y sus
opciones configuradas. La CLI de evaluación obtiene credenciales con
`DefaultAzureCredential`, mientras que la API usa OBO: comparten el flujo RAG,
pero no la identidad ni su modo de autenticación.

CI guarda la respuesta y el contexto finales, incluidas las abstenciones, para
que Azure AI Evaluation y la rúbrica complementaria apliquen el gate. La evaluación
sigue siendo un paso offline:
no se ejecuta dentro de cada petición. El grafo tampoco configura checkpoints
durables; su estado y contadores sirven a la ejecución actual.

Consulta también la [guía de carga](file-ingestion.md), la
[guía del juez](llm-as-a-judge.md) y la [guía de Entra ID](entra-auth.md).
