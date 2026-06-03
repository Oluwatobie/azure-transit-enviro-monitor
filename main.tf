# 1. The Resource Group
resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.prefix}-monitor"
  location = var.location
}

# 2. Azure Service Bus (The Message Queue)
resource "azurerm_servicebus_namespace" "sb" {
  name                = "sb-${var.prefix}-transit-${random_integer.ri.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Basic"
}

resource "random_integer" "ri" {
  min = 1000
  max = 9999
}

# 2a. The specific Queue inside the Service Bus
resource "azurerm_servicebus_queue" "queue" {
  name         = "leicester-trains"
  namespace_id = azurerm_servicebus_namespace.sb.id

  # Messages expire after 1 hour if not processed (keeps the queue clean!)
  default_message_ttl = "PT1H"
}

# 3. Azure Cosmos DB (Serverless NoSQL Database to keep costs at zero)
resource "azurerm_cosmosdb_account" "db" {
  name                = "cosmos-${var.prefix}-${random_integer.ri.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "MongoDB"

  mongo_server_version = "4.2"

  capabilities {
    name = "EnableServerless"
  }

  capabilities {
    name = "EnableMongo"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }
}

# 4. Application Insights (The Black Box Logger)
resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-${var.prefix}-workspace"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "app_insights" {
  name                = "appi-${var.prefix}-monitor"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"
}

# 5. Storage Account (Required by Azure Functions to store their background state)
resource "azurerm_storage_account" "func_sa" {
  name                     = "stfunc${var.prefix}${random_integer.ri.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# 6. Azure Container Apps Environment (The Serverless Kubernetes cluster)
resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${var.prefix}-monitor"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
}

# 7. The Container App (Your serverless compute)
resource "azurerm_container_app" "app" {
  name                         = "ca-${var.prefix}-consumer"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  template {
    container {
      name = "consumer-app"
      # We use a placeholder image for now, we will deploy your Python code over it later!
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      # Dynamic Secrets injected securely into the container
      env {
        name  = "COSMOS_CONNECTION_STRING"
        value = azurerm_cosmosdb_account.db.primary_mongodb_connection_string
      }
      env {
        name  = "SERVICE_BUS_NAMESPACE"
        value = "${azurerm_servicebus_namespace.sb.name}.servicebus.windows.net"
      }
    }
  }

  # Zero-Trust Managed Identity
  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image
    ]
  }
}

# 8. Role-Based Access Control (RBAC) - Granting the Container App passwordless access
resource "azurerm_role_assignment" "sb_sender" {
  scope                = azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Owner"
  principal_id         = azurerm_container_app.app.identity[0].principal_id
}

# 9. The Producer Container App (Runs inside your existing environment)
resource "azurerm_container_app" "producer_app" {
  name                         = "ca-${var.prefix}-producer"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  # Zero-Trust Security Identity
  identity {
    type = "SystemAssigned"
  }

  template {
    container {
      name = "producer-app"
      # We use the placeholder image so Terraform builds cleanly. GitHub Actions will overwrite this!
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "SERVICE_BUS_NAMESPACE"
        value = "${azurerm_servicebus_namespace.sb.name}.servicebus.windows.net"
      }

      # We tell this container it's acting as the PRODUCER
      env {
        name  = "APP_ROLE"
        value = "PRODUCER"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image
    ]
  }
}

# 10. The VIP Pass: Let the Producer App push data to the Service Bus securely
resource "azurerm_role_assignment" "producer_sb_sender" {
  scope                = azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_container_app.producer_app.identity[0].principal_id
}