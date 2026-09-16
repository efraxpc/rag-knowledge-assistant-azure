locals {
  # Los evaluadores integrados son identificadores del servicio y se ejecutan
  # mediante azure-ai-evaluation; no tienen un recurso ARM independiente.
  azure_rag_evaluators = {
    groundedness = {
      id        = "azureai://built-in/evaluators/groundedness"
      sdk_class = "GroundednessEvaluator"
      inputs    = ["query", "response", "context"]
    }
    relevance = {
      id        = "azureai://built-in/evaluators/relevance"
      sdk_class = "RelevanceEvaluator"
      inputs    = ["query", "response"]
    }
  }

  rag_quality_gate_configuration = {
    runtime          = "azure-ai-evaluation"
    judge_deployment = azurerm_cognitive_deployment.judge.name
    threshold        = var.rag_quality_gate_threshold
    evaluators       = local.azure_rag_evaluators
  }
}
