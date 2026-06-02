terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  
  # This tells Terraform to store the state file in the Azure vault we just made
  backend "azurerm" {
    resource_group_name  = "rg-terraform-backend"
    storage_account_name = "tfstateoluwatech13" 
    container_name       = "tfstate"
    key                  = "leicester.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}