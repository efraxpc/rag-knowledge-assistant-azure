# Flujo técnico de la aplicación y Azure

[PDF de diez hojas A4](flujo-tecnico-a4.pdf) ·
[Versión para navegador](index.html) ·
[Explicación en palabras simples](../arquitectura/arquitectura-a4.pdf)

Imprime en **A4 horizontal, al 100 %, una página por hoja**. Los márgenes son de
15 mm. El PDF y las láminas SVG contienen texto y figuras vectoriales.

| Hoja | Contenido | SVG | Mermaid |
| --- | --- | --- | --- |
| 1 | Secuencia HTTP: Streamlit, API, Entra, Search y OpenAI. | [Lámina](hojas/01-secuencia.svg) | [Fuente](hojas/01-secuencia.mmd) |
| 2 | Validación JWT, permisos delegados e intercambio OBO. | [Lámina](hojas/02-autenticacion.svg) | [Fuente](hojas/02-autenticacion.mmd) |
| 3 | Extracción, chunking, identificación e indexación de documentos. | [Lámina](hojas/03-ingestion.svg) | [Fuente](hojas/03-ingestion.mmd) |
| 4 | Recuperación textual, decisión por contexto y chat completions. | [Lámina](hojas/04-respuesta.svg) | [Fuente](hojas/04-respuesta.mmd) |
| 5 | Scopes, roles, contratos HTTP y límites de entrada. | [Lámina](hojas/05-contratos.svg) | [Recorrido de los tokens](hojas/05-contratos.mmd) |
| 6 | Directorio, registros frontend/API y consentimiento Entra. | [Lámina](hojas/06-entra-configuracion.svg) | [Fuente](hojas/06-entra-configuracion.mmd) |
| 7 | Principales, roles y scopes RBAC; autorización en cada recurso. | [Lámina](hojas/07-rbac.svg) | [Fuente](hojas/07-rbac.mmd) |
| 8 | Archivos locales, precedencia y procesos que consumen configuración. | [Lámina](hojas/08-configuracion-local.svg) | [Fuente](hojas/08-configuracion-local.mmd) |
| 9 | Origen y uso de las variables de entorno y secretos. | [Lámina](hojas/09-origen-variables.svg) | [Fuente](hojas/09-origen-variables.mmd) |
| 10 | Terraform, env/secretRef de Container Apps y GitHub Environments. | [Lámina](hojas/10-configuracion-azure.svg) | [Fuente](hojas/10-configuracion-azure.mmd) |

Las hojas describen el código revisado el **13 de septiembre de 2026**. Los
rectángulos representan operaciones y los rombos condiciones. El color verde
identifica llamadas a Azure; el rojo, respuestas de error. En la secuencia,
una flecha doble resume una llamada y su resultado. El flujo principal es el de
la home: carga textual y respuestas RAG. Los endpoints vectoriales también
aparecen en la referencia de contratos; reciben embeddings ya calculados.

## Identidad y fronteras de ejecución

El navegador interactúa con Streamlit. Es el proceso Streamlit el que hace las
peticiones HTTP a FastAPI usando `httpx`, con destino fijo configurado por
`APP_API_BASE_URL`. La primera hoja muestra el login OIDC, el callback con código
de autorización y su canje por tokens mediante Streamlit/Authlib y la credencial
del frontend. Streamlit guarda la sesión y
expone el access token para la API mediante `st.user.tokens["access"]`.

FastAPI usa `EntraTokenVerifier`:

- Firma RS256, `kid` y claves JWKS de
  `https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys`.
- `iss=https://login.microsoftonline.com/<tenant>/v2.0`;
  `aud=<client-id-api>` estricto.
- Claims obligatorios: `exp, iat, nbf, iss, aud, tid, oid, ver`;
  tolerancia temporal de 30 segundos.
- `tid` igual al tenant configurado, `ver="2.0"`, `oid` UUID válido.
- `scp` contiene `access_as_user` y `azp` coincide con el client ID de Streamlit.

Después usa `OnBehalfOfCredential` con el token de entrada como
`user_assertion` y con la credencial de la aplicación de la API. Entra emite
tokens delegados de Search y OpenAI; cada recurso aplica RBAC al usuario o grupo.
El consentimiento para emitir el token y la autorización para operar sobre el
recurso son controles distintos.

En una pregunta, las dependencias obtienen **primero el token Search y luego el
de Cognitive Services, antes de buscar contexto**. Por eso un fallo OBO de
OpenAI puede detener una consulta incluso antes de saber si Search devolverá
fragmentos. Los clientes y credenciales se cierran al terminar la petición.

Estas rutas no recurren a `az login` ni a una identidad administrada si falla
OBO. En Azure, Container Apps ejecuta FastAPI; su identidad de infraestructura
sirve para descargar la imagen, no para sustituir al usuario en Search/OpenAI.

## Entra ID: lo que se prepara antes del login

El directorio Entra contiene las cuentas y los registros de aplicación. Se usan
dos registros, ambos del tenant configurado. Sus **Application (client) IDs**
identifican a las aplicaciones. Los **Object IDs** identifican usuarios, grupos
y principales a los que se asigna RBAC; no son intercambiables con los client IDs.

| Registro | Configuración | Destino del valor |
| --- | --- | --- |
| Streamlit | Client ID y VALUE de su client secret. | TOML `[auth.microsoft].client_id` y `.client_secret`. |
| Streamlit | Plataforma Web, URI exacta de callback. | TOML `[auth].redirect_uri`; local: `http://localhost:8501/oauth2callback`. |
| Streamlit | Permiso delegado `access_as_user` de FastAPI. | `client_kwargs.scope` solicita `openid profile email api://<api-client-id>/access_as_user`. |
| FastAPI | Expose an API: `api://<api-client-id>`, scope `access_as_user`; tokens v2. | Scope del TOML y audiencia esperada por la API. |
| FastAPI | VALUE de su client secret, distinto del secreto Streamlit. | `APP_ENTRA_API_CLIENT_SECRET`; credencial de OBO. |
| FastAPI | Permisos delegados `user_impersonation` de Search y Microsoft Cognitive Services. | Consentimiento de administrador habilita la emisión de tokens OBO. |

Se puede preautorizar Streamlit en el scope expuesto por FastAPI. La cuenta debe
ser miembro o invitada admitida en el tenant. La configuración del registro y el
consentimiento habilitan el intercambio OAuth; los roles de datos siguen siendo
necesarios para ejecutar la operación.

Terraform utiliza los registros existentes. La opción
`manage_entra_openai_access=true` administra el permiso de Cognitive Services y
su consentimiento; no crea los dos registros ni configura todos los permisos de
Streamlit/Search. `create_entra_api_client_secret=true` puede crear una credencial
adicional en el registro existente de FastAPI.

## RBAC: quién tiene permiso y sobre qué recurso

Una asignación RBAC combina **principal + rol + scope del recurso**.
Se configura en Azure Portal, en el recurso → **Access control (IAM)**, o mediante
las asignaciones Terraform. El scope OAuth de un token y el scope de una asignación
RBAC son conceptos distintos: el primero pide acceso a un destinatario; el segundo
delimita dónde se aplica el rol.

| Principal | Rol | Scope RBAC | Operación |
| --- | --- | --- | --- |
| Usuario/grupo de la aplicación | `Search Index Data Contributor` | Recurso Azure AI Search. | Cargar y consultar los fragmentos de la home. |
| Usuario/grupo de la aplicación | `Cognitive Services OpenAI User` | Cuenta Azure OpenAI. | Generar respuestas mediante el modelo. |
| Identidad Container Apps | `AcrPull` | Container Registry. | Descargar la imagen; no sustituye al usuario en Search/OpenAI. |
| Identidad GitHub `evaluation` | `Search Index Data Contributor` + `Cognitive Services OpenAI User` | Search y cuenta OpenAI, respectivamente. | Generar/evaluar casos en el índice CI. |
| Identidad GitHub `production` | `Container Registry Tasks Contributor` | Container Registry. | Construir la imagen mediante ACR Tasks. |
| Identidad GitHub `production` | `Container Apps Contributor` | Container App de la API. | Actualizar la imagen aprobada. |

Terraform asigna Search al grupo indicado por `search_user_group_object_id`.
Se obtiene en **Entra ID → Groups → grupo → Object ID**. La variable
`openai_user_object_ids` asigna OpenAI a usuarios concretos; los IDs se obtienen
en **Entra ID → Users → usuario → Object ID**. El código permite autorización
mediante grupos, pero esta variable Terraform de OpenAI recibe usuarios. Para
un grupo OpenAI, la asignación se prepara por separado en IAM.

Los roles de datos no permiten administrar todo el servicio. Para preparar el
índice, Terraform usa una asignación `Search Service Contributor` al principal
administrativo. La identidad de administración, las de CI y el usuario OBO tienen
trabajos diferentes. Las identidades de GitHub reciben tokens temporales por
OIDC; no usan el client secret de FastAPI.

## Configuración local: origen → archivo → consumidor

Los ejemplos contienen marcadores. Copiarlos no consulta Azure ni completa
automáticamente sus valores. Desde la raíz, se prepara `.env` a partir de
`.env.example` y `.streamlit/secrets.toml` a partir de su ejemplo. El proceso
`Settings` lee `.env` directamente; el launcher no hace `source` del archivo.

| Variable de `.env` | Dónde obtenerla | Consumidor |
| --- | --- | --- |
| `APP_ENTRA_TENANT_ID` | Entra ID → Overview → Directory (tenant) ID. | Issuer/tenant JWT y tenant de OBO. |
| `APP_ENTRA_API_CLIENT_ID` | App registration FastAPI → Application (client) ID. | Audiencia JWT y client ID de OBO. |
| `APP_ENTRA_FRONTEND_CLIENT_ID` | App registration Streamlit → Application (client) ID. | Verificación de `azp`; mismo ID del cliente OIDC del TOML. |
| `APP_ENTRA_API_CLIENT_SECRET` | Registro FastAPI → Certificates & secrets → **VALUE**. | Credencial de OBO; no se usa el Secret ID. |
| `APP_AZURE_SEARCH_ENDPOINT` | Recurso Search → endpoint; output `search_service_endpoint`. | Endpoint de `SearchClient`. |
| `APP_AZURE_SEARCH_TEXT_INDEX_NAME` | Search → Indexes → nombre exacto; Terraform crea `rag-text-chunks`. | Índice textual de `SearchClient`; no hay output de nombre del índice productivo en el código actual. |
| `APP_AZURE_OPENAI_ENDPOINT` | Endpoint del recurso Azure AI Services/OpenAI; output `azure_openai_endpoint`. | Raíz HTTPS del cliente; sin `/openai/v1`. |
| `APP_AZURE_OPENAI_CHAT_DEPLOYMENT` | Nombre exacto del deployment; output `azure_openai_chat_deployment_name`. | Campo `model` de la llamada chat; no basta el nombre comercial del modelo. |
| `APP_API_BASE_URL` | Local: host/puerto de la API; publicada: output `container_app_url`. | Destino HTTP de Streamlit. |

Los outputs se obtienen desde `infrastructure/terraform` con
`terraform output <nombre>` para los valores no secretos indicados. Esta lectura
no aplica infraestructura.

| Campo de `.streamlit/secrets.toml` | Origen | Uso |
| --- | --- | --- |
| `[auth.microsoft].client_id` | Client ID del registro Streamlit. | Cliente del intercambio OIDC. |
| `[auth.microsoft].client_secret` | VALUE del secreto del registro Streamlit. | Canje del código de autorización; distinto del secreto API. |
| `[auth].redirect_uri` | URL del hosting UI + `/oauth2callback`. | Debe coincidir con la URI Web registrada en Entra. |
| `[auth].cookie_secret` | Aleatorio generado localmente. | Firma cookies de Streamlit; no viene de Azure. |
| `[auth].expose_tokens` | Configuración `['access']`. | Hace disponible el access token para llamar a la API. |
| `[auth.microsoft].server_metadata_url` | `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration`. | Descubrimiento de endpoints/claves OIDC de Entra. |
| `[auth.microsoft].client_kwargs.scope` | Scope que expone el registro API. | `openid profile email api://<api-client-id>/access_as_user`. |

El `cookie_secret` se puede generar con
`python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
El tenant y el API ID del TOML se completan manualmente: sus marcadores no se
sustituyen desde `.env`.

Para `Settings`, **environment del proceso > `.env` > defaults**.
`run_local.sh` exporta `APP_API_BASE_URL` usando el valor ya presente en el
environment o los hosts/puertos del launcher. Por eso al usar ese script, un
`APP_API_BASE_URL` escrito solo en `.env` puede quedar sobreescrito por el launcher.
Los dos procesos heredan la variable exportada. Las demás configuraciones `APP_*`
se leen mediante `get_settings()` en cada proceso. Los tokens se generan durante
OIDC/OBO y no se colocan en estos archivos.

Configuración adicional: `APP_AZURE_OPENAI_JUDGE_DEPLOYMENT` y
`APP_LLM_JUDGE_TIMEOUT_SECONDS` son para evaluación; el flujo HTTP de preguntas
usa el deployment chat y `APP_RAG_GENERATION_TIMEOUT_SECONDS`. El índice y las
dimensiones vectoriales son opcionales y distintos del índice textual.
`APP_AZURE_MANAGED_IDENTITY_CLIENT_ID` se reserva para comandos administrativos o
evaluación; no cambia la identidad de las peticiones HTTP.

## Azure: quién inyecta las variables y el secreto

Terraform escribe la configuración de la Container App. No copia `.env` a la
imagen ni conecta actualmente Key Vault como proveedor de secretos.

| Variable de Container Apps | Fuente Terraform |
| --- | --- |
| `APP_AZURE_SEARCH_ENDPOINT` | `azurerm_search_service.main.endpoint`. |
| `APP_AZURE_SEARCH_TEXT_INDEX_NAME` | `azapi_data_plane_resource.text_index.name`. |
| `APP_AZURE_OPENAI_ENDPOINT` | `data.azurerm_cognitive_account.openai.endpoint`. |
| `APP_AZURE_OPENAI_CHAT_DEPLOYMENT` | `azurerm_cognitive_deployment.general.name`. |
| `APP_ENTRA_TENANT_ID` | Input `entra_tenant_id`. |
| `APP_ENTRA_API_CLIENT_ID` | Input `entra_api_client_id`. |
| `APP_ENTRA_FRONTEND_CLIENT_ID` | Input `entra_frontend_client_id`. |
| `APP_ENTRA_API_CLIENT_SECRET` | Referencia `secret_name = 'entra-api-client-secret'`. |
| `APP_ENVIRONMENT` / `APP_DEBUG` | Input `container_app_environment` / literal `false`. |

La credencial API se suministra mediante `TF_VAR_entra_api_client_secret` o se
crea opcionalmente en el registro existente. Terraform guarda su valor en el
secret de Container Apps **`entra-api-client-secret`** y conecta la variable de
entorno a ese secret. El valor también se conserva en el estado de Terraform.
`.env` y el TOML real permanecen fuera de Git.

Key Vault está provisionado; no hay lectura `SecretClient` ni referencia Key
Vault en este flujo. Streamlit no es desplegado por este Terraform: su hosting
necesita el TOML OIDC y `APP_API_BASE_URL` por separado. El contenedor API no
recibe el deployment juez ni configuración vectorial de esta plantilla.

## GitHub Environments: variables de los jobs

Los outputs de Terraform se copian manualmente a las **Environment variables**
de GitHub, en `evaluation` y `production`. Terraform no crea esos entornos ni
rellena sus variables. El workflow actual consume `vars.*`, no `secrets.*`.

| Variable GitHub | Origen | Destino |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | Output `github_evaluation_identity_client_id` o `github_production_identity_client_id`, según entorno. | `azure/login` con OIDC; identidad distinta por trabajo. |
| `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Contexto Azure; campos del output `azure_connection`. | Contexto de login Azure. |
| `EVAL_AZURE_SEARCH_ENDPOINT` | Output `search_service_endpoint`. | Runner `APP_AZURE_SEARCH_ENDPOINT`. |
| `EVAL_AZURE_SEARCH_TEXT_INDEX_NAME` | Output `search_evaluation_index_name`. | Runner `APP_AZURE_SEARCH_TEXT_INDEX_NAME`; índice separado de CI. |
| `EVAL_AZURE_OPENAI_ENDPOINT` | Output `azure_openai_endpoint`. | Runner `APP_AZURE_OPENAI_ENDPOINT`. |
| `EVAL_AZURE_OPENAI_CHAT_DEPLOYMENT` | Output `azure_openai_chat_deployment_name`. | Runner `APP_AZURE_OPENAI_CHAT_DEPLOYMENT`. |
| `EVAL_AZURE_OPENAI_JUDGE_DEPLOYMENT` | Output `azure_openai_judge_deployment_name`. | Runner `APP_AZURE_OPENAI_JUDGE_DEPLOYMENT`. |
| `AZURE_CONTAINER_REGISTRY_NAME` / `AZURE_CONTAINER_IMAGE_REPOSITORY` | Nombre del ACR existente / repositorio de imagen configurado. | Job production: `az acr build`. |
| `AZURE_CONTAINER_APP_RESOURCE_GROUP` / `AZURE_CONTAINER_APP_NAME` | Nombres de RG y Container App de la API. | Job production: `az containerapp update`. |

Las variables del runner sirven a los comandos CI. No se transfieren
automáticamente al contenedor API. El deploy actual cambia la imagen; Terraform
mantiene la configuración `env`/secrets de Container Apps.

## Detalles de datos

La carga normaliza el nombre del archivo y calcula:

```text
document_id = SHA256(source.encode("utf-8") + b"\0" + file_bytes)
chunk_id    = "page-<page-or-0>-offset-<start>"
index_id    = SHA256(JSON([document_id, chunk_id]).encode("utf-8"))
```

El último hash usa la serialización JSON de Python con `ensure_ascii=False`.
Los chunks contienen `document_id, content, source, page`, además de su ID.
En el índice, el ID del chunk se guarda como `chunk_id`; `id` es la clave hash.

El chunking opera por página, normaliza saltos de línea y usa ventanas de
1000 caracteres con solape de 200. PDF usa `pypdf`; TXT/MD usan
`utf-8-sig`, con página nula. Las páginas sin texto generan avisos; un archivo
sin texto extraíble produce 422. No se guarda el archivo original.

La carga textual limita los lotes a 1000 registros y una estimación conservadora
de 15 000 000 bytes, con margen para el envoltorio del SDK. La indexación puede
guardar parte de un lote antes de fallar. Los IDs deterministas permiten
reintentar el mismo archivo; no es una transacción atómica.

La búsqueda textual pasa `search_text=question` y `top=top_k` a SearchClient.
Si llega `document_id`, añade un filtro OData y escapa las comillas simples.
La home lo envía siempre y usa `top_k=5`; la API permite omitirlo y admite
`top_k` entre 1 y 20.

`AnswerService` construye el contexto con `content, source, page`. El prompt
de sistema pide usar solo esas fuentes y citarlas; el mensaje de usuario incluye
la pregunta y el contexto como JSON delimitado. El adaptador llama:

```text
POST <APP_AZURE_OPENAI_ENDPOINT>/openai/v1/chat/completions
Authorization: Bearer <token Cognitive Services>
model = APP_AZURE_OPENAI_CHAT_DEPLOYMENT
max_completion_tokens = 2000
```

Se valida que exista contenido textual no vacío y que no haya rechazo del
modelo. La respuesta incluye `answer` y `context: list[SearchHit]`; cada hit
contiene IDs, contenido, fuente, página y score. No hay verificación automática
de todas las afirmaciones generadas durante la petición.

Timeouts actuales: carga desde UI 120 s, pregunta desde UI 90 s, conexión UI
5 s. El timeout de generación en la API es configurable; valor predeterminado
60 s. Son configuraciones de timeout de los clientes, no garantías de duración.

## Códigos de error

Los diagramas muestran las ramas principales. Esta tabla precisa los códigos:

| HTTP | Código | Causa |
| --- | --- | --- |
| 401 | `authentication_required` | Bearer ausente o JWT inválido/caducado. |
| 403 | `insufficient_delegated_permission` | `scp` o `azp` incorrectos. |
| 403 | `delegated_authentication_failed` | Entra rechaza el intercambio OBO. |
| 403 | `search_access_denied` | Search rechaza la operación del usuario. |
| 413 | `file_too_large` / `chunk_too_large` | Archivo o fragmento excede su límite. |
| 415 | `unsupported_file_type` | Extensión distinta de PDF, TXT o MD. |
| 422 | `invalid_document` | Nombre, codificación, PDF o contenido no válido. |
| 422 | `invalid_embedding_dimensions` / `invalid_embedding` | Dimensión incorrecta o vector nulo. |
| 502 | `chunk_indexing_failed` | Algún registro no se indexó; puede haber escrituras parciales. |
| 502 | `invalid_text_search_response` / `invalid_vector_store_response` | Respuesta de Search incompatible. |
| 502 | `rag_provider_error` | Fallo del adaptador OpenAI: token, HTTP, rechazo o contenido inválido. |
| 503 | `authentication_not_configured` / `identity_provider_unavailable` | Configuración de identidad ausente o Entra/JWKS no disponibles. |
| 503 | `text_store_not_configured` / `rag_generator_not_configured` / `vector_store_not_configured` | Falta configurar el servicio. |
| 503 | `text_store_unavailable` / `text_search_unavailable` / `vector_store_unavailable` | Operación Search no disponible. |

Un HTTP 403 de OpenAI durante la llamada de chat se transforma en
**502 `rag_provider_error`**. Un rechazo en la preparación OBO se transforma en
**403 `delegated_authentication_failed`**. La etapa del fallo importa.

`ApplicationError` devuelve `{"error":{"code":...,"message":...,"details":...}}`.
El 401 agrega `WWW-Authenticate: Bearer`.
Un error de validación de petición FastAPI/Pydantic devuelve 422 con su formato
habitual `detail`. Las dependencias se resuelven antes del handler; el diagrama
no supone que toda validación del cuerpo ocurra antes de OBO.

## Editar y regenerar

El [generador](generate.py) necesita Python 3.11+ y Matplotlib 3.10 y contiene
sus propias funciones de dibujo.
Desde la raíz del repositorio:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib python3 docs/diagrams/flujo-tecnico/generate.py
```

Añade `--preview-dir /tmp/rag-technical-preview` para guardar PNG de revisión.
Las hojas 2–4, 6–8 y 10 generan SVG/PDF y Mermaid desde las mismas definiciones de
nodos y conexiones. La hoja 1 tiene una versión Mermaid de la secuencia; la hoja 9
complementa la tabla con un flujo de orígenes y consumidores. En la hoja 5,
Mermaid representa el recorrido de los tokens; los contratos se presentan como
tabla en el PDF/SVG. Mermaid puede distribuir los nodos de otra manera.

## Fuentes en el repositorio

- [Login](../../../app/ui_auth.py) e [interfaz HTTP](../../../app/streamlit_app.py).
- [Validación JWT](../../../app/core/auth.py) y [OBO/clientes](../../../app/core/resources.py).
- [Dependencias FastAPI](../../../app/api/dependencies.py).
- [Carga](../../../app/services/file_ingestion.py), [extracción](../../../app/services/extraction.py) y [chunking](../../../app/services/chunking.py).
- [Adaptador textual](../../../app/integrations/azure_text_search.py) y [vectorial](../../../app/integrations/azure_search.py).
- [Servicio RAG](../../../app/services/answer.py) y [cliente OpenAI](../../../app/integrations/azure_openai_chat.py).
- [Modelos y límites](../../../app/rag/models.py) y [errores](../../../app/core/exceptions.py).
- [Guía de autenticación](../../entra-auth.md).
- [Ejemplo .env](../../../.env.example) y [ejemplo TOML](../../../.streamlit/secrets.toml.example).
- [Launcher local](../../../scripts/run_local.sh) y [lectura de settings](../../../app/core/config.py).
- [Registros/permisos Entra](../../../infrastructure/terraform/entra.tf).
- [RBAC Search](../../../infrastructure/terraform/search.tf), [OpenAI](../../../infrastructure/terraform/openai.tf) e [identidades GitHub](../../../infrastructure/terraform/github_oidc.tf).
- [Variables/secrets del contenedor](../../../infrastructure/terraform/container_app.tf) y [outputs](../../../infrastructure/terraform/outputs.tf).
- [Mapeo de variables CI](../../../.github/workflows/quality-gate-deploy.yml).
