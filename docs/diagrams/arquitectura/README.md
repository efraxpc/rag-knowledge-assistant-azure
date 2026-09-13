# El flujo completo de la aplicación y sus partes de Azure

[Abrir el PDF para imprimir](arquitectura-a4.pdf) ·
[Ver las hojas en el navegador](index.html)

Cinco hojas con palabras simples. Empieza por el recorrido general y sigue las
etapas: entrar, guardar el documento y hacer una pregunta. Cada paso indica
quién actúa y qué hace. Los recuadros de la derecha explican el servicio de Azure
que interviene.

Imprime en **A4 horizontal, a tamaño real / 100 %, una página por hoja**.
Los márgenes laterales son de al menos 15 mm. Los nombres y números permiten
seguir la explicación también en blanco y negro. Desde el navegador, desactiva
sus encabezados y pies de página.

| Hoja | Qué explica | Archivo editable |
| --- | --- | --- |
| 1 | El recorrido completo: quién envía cada petición y quién responde. | [Flujo completo](hojas/01-flujo-completo.svg) |
| 2 | Cómo Entra ID comprueba la cuenta y vuelves a la home. | [Inicio de sesión](hojas/02-iniciar-sesion.svg) |
| 3 | Cómo la API prepara el documento y Search guarda su texto. | [Guardar el documento](hojas/03-guardar-documento.svg) |
| 4 | Cómo Search encuentra información y OpenAI redacta; qué ocurre si falta texto. | [Hacer una pregunta](hojas/04-preguntar.svg) |
| 5 | Qué hace cada servicio de Azure, incluidos los que sostienen la API publicada. | [Partes de Azure](hojas/05-partes-azure.svg) |

## Cómo leer el recorrido

En la primera hoja, cada columna es una pieza. Lee las flechas de arriba hacia
abajo. Una flecha doble resume el envío y el regreso. Los pasos 1–2 muestran la
entrada, 3–7 la carga, y 8–12 la pregunta. Las hojas siguientes explican cada
etapa con más espacio y reinician la numeración.

**Streamlit** es tu pantalla. **FastAPI** coordina el trabajo.
**Microsoft Entra ID** comprueba tu cuenta y entrega pases temporales, llamados
tokens. **Azure AI Search** guarda y busca partes del documento.
**Azure OpenAI** redacta usando el texto que recibe de la API.

La API lleva la información entre Search y OpenAI. Search devuelve sus
resultados a la API; la API prepara la pregunta y los fragmentos para OpenAI.

## Alcance de la explicación

El diagrama corresponde al código revisado el **13 de septiembre de 2026**.
Las cuatro primeras hojas muestran el uso local con Azure. En la quinta se
explica también el alojamiento de la API publicada.

La API valida el pase recibido de la pantalla y pide a Entra acceso a los
servicios en nombre del usuario. Se necesitan consentimiento de la aplicación
y roles del usuario o su grupo. Iniciar sesión por sí solo no concede todos
esos permisos.

La carga admite PDF con texto, TXT y Markdown, hasta 10 MiB. La API extrae y
divide el texto. Search conserva los fragmentos y sus referencias; el archivo
original no queda almacenado. La carga de la home no aplica OCR ni genera
embeddings. Las preguntas usan el documento cargado en esa sesión y buscan
hasta cinco fragmentos.

La API prepara los tokens de Search y OpenAI antes de buscar. Si la búsqueda
no devuelve texto, responde con un aviso sin solicitar una generación. Cuando
hay texto, pide al modelo responder usando esas fuentes y citarlas. La aplicación
muestra la respuesta y los fragmentos; no verifica automáticamente todas las
afirmaciones del modelo.

Cognitive Services es el nombre del recurso de autorización usado para Azure
OpenAI. El permiso solicitado es
`https://cognitiveservices.azure.com/.default`.
Search usa `https://search.azure.com/.default`.
Azure Machine Learning no participa en este recorrido.

Container Apps ejecuta la API publicada; Streamlit requiere alojamiento por
separado. Container Registry guarda su imagen y Log Analytics recibe los
registros del entorno. Key Vault está preparado por Terraform, pero la API
actual no lo consulta directamente.

El [flujo completo en ocho hojas A4](../flujo-completo/flujo-completo-a4.pdf)
complementa estas láminas con preparación, errores frecuentes y publicación.
GitHub Actions prueba y evalúa las respuestas antes de publicar. Terraform
prepara la infraestructura y reutiliza la cuenta OpenAI y el registro de imágenes
existentes; esas tareas tienen identidades distintas al acceso del usuario.

## Regenerar los archivos

El PDF y los SVG contienen texto y figuras vectoriales para imprimir con
nitidez. Modifica [generate.py](generate.py) para cambiar la explicación.
Este script reutiliza funciones del
[generador del flujo completo](../flujo-completo/generate.py).

Necesitas **Python 3.11 o superior y Matplotlib 3.10**. Desde la raíz del proyecto:

`MPLCONFIGDIR=/tmp/rag-flow-matplotlib python3 docs/diagrams/arquitectura/generate.py`

Añade `--preview-dir /tmp/rag-application-flow-preview` para guardar también
vistas previas PNG. Esta dependencia se usa solo para producir los diagramas.

## Código y documentación usados

- [Interfaz](../../../app/streamlit_app.py).
- [Inicio de sesión](../../../app/ui_auth.py).
- [Autenticación y permisos](../../entra-auth.md).
- [Acceso a Azure en nombre del usuario](../../../app/core/resources.py).
- [Preparación del archivo](../../../app/services/file_ingestion.py).
- [Búsqueda textual](../../../app/integrations/azure_text_search.py).
- [Generación de respuestas](../../../app/services/answer.py).
- [Infraestructura](../../../infrastructure/terraform/README.md).
- [Pruebas y publicación](../../../.github/workflows/quality-gate-deploy.yml).
