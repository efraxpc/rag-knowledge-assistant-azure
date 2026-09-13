# Arquitectura del proyecto en cuatro hojas A4

[Abrir el PDF para imprimir](arquitectura-a4.pdf) ·
[Ver las hojas en el navegador](index.html)

Imprime en **A4 horizontal**, a **tamaño real / 100 %**, una página por hoja.
Los márgenes laterales son de 15 mm. Las flechas y los números permiten seguir
la explicación también en blanco y negro. Si imprimes desde el navegador,
desactiva sus encabezados y pies de página.

| Hoja | Qué explica | Archivo editable |
| --- | --- | --- |
| 1 | Qué funciona en tu equipo, qué funciona en Azure y cómo se conectan. | [Mapa general](hojas/01-mapa-general.svg) |
| 2 | Cómo la API recibe una petición, reparte el trabajo y usa Azure. | [Dentro de la API](hojas/02-dentro-de-la-api.svg) |
| 3 | Los ocho pasos que sigue una pregunta hasta mostrar la respuesta. | [Recorrido de una pregunta](hojas/03-recorrido-pregunta.svg) |
| 4 | Cómo se prepara la infraestructura y se publica la API en Azure. | [Publicación en Azure](hojas/04-publicacion-azure.svg) |

Estas hojas complementan el [flujo completo en ocho hojas A4](../flujo-completo/flujo-completo-a4.pdf),
que explica con más detalle el inicio de sesión, la carga de documentos, los
tokens y la solución de errores.

## Qué representa el diagrama

La explicación corresponde al código revisado el **13 de septiembre de 2026**.
Las tres primeras hojas muestran el uso local; la última muestra la publicación
de la API configurada en el repositorio.

- **Streamlit** es la pantalla donde inicias sesión, subes archivos y preguntas.
- **FastAPI** recibe esas peticiones y coordina el trabajo.
- **Entra ID** comprueba la identidad y entrega los tokens, comprobantes
  temporales de acceso. La API solicita acceso a Azure en nombre del usuario.
- **AI Search** guarda y busca los fragmentos de texto. La carga de la home
  no conserva el archivo original ni genera embeddings o aplica OCR.
- **Azure OpenAI** recibe la pregunta y el texto encontrado para redactar la
  respuesta. Su token usa el recurso Cognitive Services; la hoja 6 del flujo
  completo explica ese nombre.

La API obtiene los permisos de Search y OpenAI antes de buscar. Si no encuentra
fragmentos, muestra un aviso de información insuficiente sin pedir una respuesta
al modelo. El diagrama de la pregunta resume el recorrido de una petición válida.

En la publicación, Terraform prepara los recursos y reutiliza un Container
Registry y una cuenta Azure OpenAI existentes. GitHub Actions comprueba el código
y la calidad de las respuestas antes de publicar una imagen. Container Apps ejecuta la API.
Streamlit necesita alojamiento por separado y debe apuntar a esa API.
Las identidades de evaluación y publicación son distintas del acceso delegado
del usuario durante el uso de la aplicación.

Log Analytics recoge registros del entorno. Terraform también prepara Key Vault
como almacén de secretos, pero la aplicación actual no lo consulta directamente.
La configuración y los servicios de apoyo se resumen para que las flechas
principales sean fáciles de seguir.

## Regenerar los archivos

El PDF y los SVG contienen figuras y texto vectoriales. El contenido se puede
modificar en [generate.py](generate.py), que reutiliza las funciones de dibujo
del [generador del flujo completo](../flujo-completo/generate.py).

Necesitas **Python 3.11 o superior y Matplotlib 3.10** para regenerarlos. Esta
dependencia solo se usa para crear los diagramas. Desde la raíz del repositorio:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib \
  python3 docs/diagrams/arquitectura/generate.py
```

Puedes añadir `--preview-dir /tmp/rag-architecture-preview` para guardar vistas
previas en PNG además del PDF y las hojas SVG.

## Código y documentación usados

- [Interfaz](../../../app/streamlit_app.py).
- [Autenticación y permisos](../../entra-auth.md).
- [Acceso a Azure en nombre del usuario](../../../app/core/resources.py).
- [Carga de documentos](../../file-ingestion.md).
- [Búsqueda y generación de respuestas](../../../app/services/answer.py).
- [Infraestructura](../../../infrastructure/terraform/README.md).
- [Pruebas y publicación](../../../.github/workflows/quality-gate-deploy.yml).
