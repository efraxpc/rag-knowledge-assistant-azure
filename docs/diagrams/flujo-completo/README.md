# Flujo completo del proyecto en ocho hojas A4

[Abrir el PDF para imprimir](flujo-completo-a4.pdf) ·
[Ver las hojas en el navegador](index.html)

Imprime en **A4 vertical**, a **tamaño real / 100 %**, una página por hoja.
El contenido deja 17 mm a cada lado y también se lee en blanco y negro.
Si imprimes la versión del navegador, desactiva sus encabezados y pies de página.

| Hoja | Explicación | Archivo editable |
| --- | --- | --- |
| 1 | El recorrido desde que abres la página hasta que recibes una respuesta. | [Vista general](hojas/01-vista-general.svg) |
| 2 | Lo que se prepara en Azure y en tu equipo antes de empezar. | [Preparación](hojas/02-preparacion.svg) |
| 3 | Cómo Microsoft comprueba tu cuenta y vuelves a la home. | [Inicio de sesión](hojas/03-iniciar-sesion.svg) |
| 4 | Cómo se recibe el documento, se divide su texto y se guarda. | [Carga de documentos](hojas/04-subir-documentos.svg) |
| 5 | Cómo se buscan fragmentos y se obtiene una respuesta con fuentes. | [Preguntas](hojas/05-hacer-preguntas.svg) |
| 6 | Qué token usa cada servicio y por qué aparece Cognitive Services. | [Tokens y permisos](hojas/06-tokens-permisos.svg) |
| 7 | Dónde se detiene el flujo cuando hay un error y cómo continuar. | [Errores frecuentes](hojas/07-resolver-errores.svg) |
| 8 | Cómo se prueba y se publica una nueva versión de la API. | [Publicación](hojas/08-publicar-version.svg) |

Las hojas describen el código del proyecto revisado el **13 de septiembre de
2026**. El flujo de uso es local con servicios de Azure; la última hoja describe
el proceso de publicación configurado en GitHub. La búsqueda de la interfaz es
textual. El proyecto también tiene endpoints vectoriales para datos ya
preparados, pero no forman parte de la carga y las preguntas de la home.

La API pide acceso a Search y OpenAI antes de ejecutar una pregunta. Si la
búsqueda no devuelve fragmentos, responde con el aviso de información
insuficiente sin solicitar al modelo que genere una respuesta.

## Regenerar los archivos

El PDF contiene texto y figuras vectoriales, que mantienen su calidad al
imprimir. Cada hoja también se guarda en SVG. El contenido y la distribución
se pueden modificar en [generate.py](generate.py).

El generador necesita **Python 3.11 o superior y Matplotlib 3.10**. Esta
dependencia es solo para producir los diagramas; no cambia la instalación de
la aplicación. Desde la raíz del repositorio, con un Python que tenga
Matplotlib instalado:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib \
  python3 docs/diagrams/flujo-completo/generate.py
```

Para guardar vistas previas PNG durante la revisión:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib \
  python3 docs/diagrams/flujo-completo/generate.py \
    --preview-dir /tmp/rag-flow-preview
```

## Base de la explicación

- [Inicio de sesión y permisos](../../entra-auth.md).
- [Carga de archivos](../../file-ingestion.md).
- [Evaluación y publicación](../../llm-as-a-judge.md).
- [Interfaz principal](../../../app/streamlit_app.py).
- [Acceso a Azure en nombre del usuario](../../../app/core/resources.py).
- [Búsqueda y generación de respuestas](../../../app/services/answer.py).
- [Flujo de publicación de GitHub](../../../.github/workflows/quality-gate-deploy.yml).
- [Autenticación de Azure OpenAI documentada por Microsoft](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat).
