provider "azuread" {
  tenant_id = var.entra_tenant_id
}

data "azuread_application" "api" {
  count     = var.create_entra_api_client_secret || var.manage_entra_openai_access ? 1 : 0
  client_id = var.entra_api_client_id

  lifecycle {
    precondition {
      condition     = var.entra_api_client_id != null && var.entra_tenant_id != null
      error_message = "Para administrar Entra, configura entra_api_client_id y entra_tenant_id."
    }
  }
}

data "azuread_service_principal" "api" {
  count     = var.manage_entra_openai_access ? 1 : 0
  client_id = var.entra_api_client_id
}

data "azuread_service_principal" "cognitive_services" {
  count     = var.manage_entra_openai_access ? 1 : 0
  client_id = "7d312290-28c8-473c-a0ed-8e53749b6d6d"
}

# Administra solo los permisos de esta API; conserva Search y Microsoft Graph.
resource "azuread_application_api_access" "openai" {
  count          = var.manage_entra_openai_access ? 1 : 0
  application_id = data.azuread_application.api[0].id
  api_client_id  = data.azuread_service_principal.cognitive_services[0].client_id
  scope_ids = [
    data.azuread_service_principal.cognitive_services[0].oauth2_permission_scope_ids["user_impersonation"]
  ]
}

resource "azuread_service_principal_delegated_permission_grant" "openai" {
  count                                = var.manage_entra_openai_access ? 1 : 0
  service_principal_object_id          = data.azuread_service_principal.api[0].object_id
  resource_service_principal_object_id = data.azuread_service_principal.cognitive_services[0].object_id
  claim_values                         = ["user_impersonation"]

  depends_on = [azuread_application_api_access.openai]
}

# Añade una credencial propia sin reemplazar las credenciales de otros clientes.
resource "azuread_application_password" "container_app" {
  count          = var.create_entra_api_client_secret ? 1 : 0
  application_id = data.azuread_application.api[0].id
  display_name   = "terraform-container-app-obo"

  lifecycle {
    precondition {
      condition     = nonsensitive(var.entra_api_client_secret == null)
      error_message = "Usa una credencial proporcionada o una administrada por Terraform, no ambas."
    }
  }
}
