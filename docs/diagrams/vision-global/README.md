# Visión técnica global en una página

[PDF de una página A4](vision-global-a4.pdf) ·
[Ver en el navegador](index.html) ·
[SVG vectorial](vision-global.svg) ·
[Fuente Mermaid](vision-global.mmd)

Esta lámina resume el flujo de la aplicación, Entra ID, RBAC, el origen de la
configuración y la publicación en Azure. Complementa el
[diagrama técnico de diez hojas](../flujo-tecnico/flujo-tecnico-a4.pdf),
que se conserva con sus fuentes y explicaciones.

Imprime en **A4 horizontal, al 100 %**. El PDF contiene una sola página.
En el navegador, desactiva encabezados y pies de impresión. El SVG permite
ampliar el diagrama conservando la nitidez.

## Cómo seguir el mapa

La fila superior muestra origen, ubicación y consumidor de la configuración.
La parte central muestra las llamadas de la aplicación:

1. Streamlit inicia OIDC con Entra; el callback y el canje del código producen
   los tokens de sesión.
2. El proceso Streamlit envía el token API con la carga o la pregunta a FastAPI.
3. FastAPI valida el JWT y usa OBO con la credencial API para obtener tokens de
   Azure que representan al usuario.
4. Search almacena los chunks de la carga o recupera el contexto de la pregunta.
5. Con contexto, la API envía pregunta y texto a OpenAI y recibe la respuesta.
   Sin contexto, devuelve un aviso sin llamar al chat.
6. La respuesta vuelve a Streamlit y se presenta al usuario.

Las flechas dobles de Search y OpenAI resumen llamada y resultado. Las flechas
de Entra resumen los intercambios; sus respuestas se detallan en el PDF de diez
hojas. Las líneas discontinuas representan configuración y las continuas,
llamadas durante el uso. Los cruces de líneas sin punto no son conexiones.

Los tokens de Search y OpenAI se obtienen antes de buscar contexto durante una
pregunta. OBO usa los permisos del usuario, mientras la identidad de Container
Apps usa `AcrPull` para descargar la imagen.

La fila inferior resume CI y los servicios de apoyo. GitHub Environments usa
variables e identidades OIDC separadas para evaluación y producción. Terraform
mantiene variables y secretos de Container Apps; CI actualiza la imagen.
Key Vault está preparado, sin conexión de secretos a la API actual.

## Configuración resumida

- **UI:** `.streamlit/secrets.toml` contiene cliente/secreto del registro frontend,
  tenant para metadata, scope de la API, callback y cookie secret aleatorio.
  `APP_API_BASE_URL` llega a Streamlit mediante Settings/environment.
- **Local:** `.env` contiene `APP_ENTRA_*` y `APP_AZURE_*`: IDs/credencial API de
  Entra y endpoints/índice/deployment de Azure. El environment prevalece sobre
  `.env`, seguido de defaults.
- **Azure:** Terraform configura `env APP_*` y referencia el secret
  `entra-api-client-secret`. La credencial API procede del registro de Entra,
  suministrada o creada mediante la opción de Terraform.
- **RBAC:** Search requiere `Search Index Data Contributor` para la carga de la
  home; OpenAI requiere `Cognitive Services OpenAI User`. Los roles se asignan
  al usuario/grupo sobre cada recurso, usando Object IDs.

Los nombres completos de variables, outputs, permisos, scopes y rutas de error
se mantienen en la [documentación técnica detallada](../flujo-tecnico/README.md).
La home guarda texto dividido y realiza búsqueda textual. Los endpoints
vectoriales y la referencia exhaustiva de contratos figuran en el PDF detallado.

## Editar y regenerar

El [generador](generate.py) necesita Python 3.11+ y Matplotlib 3.10.
Desde la raíz del proyecto:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib python3 docs/diagrams/vision-global/generate.py
```

Para generar una vista previa PNG, añade
`--preview /tmp/rag-global-preview.png`.
El script escribe únicamente los archivos de esta carpeta; no regenera ni
modifica el PDF de diez hojas.

El PDF/SVG y Mermaid muestran los mismos conceptos. Mermaid distribuye las
relaciones automáticamente y desarrolla algunos intercambios que se resumen
en las flechas de la lámina.
