// Infra do previsor de imóveis — desenhada para custo ~zero na conta pessoal:
//  - Container Apps com minReplicas 0 (scale-to-zero: não paga quando ninguém usa)
//  - imagem pública no ghcr.io (sem Azure Container Registry)
//  - Functions no plano Consumption (1M execuções grátis/mês)
//  - Log Analytics limitado a 30 dias de retenção
// Deploy: az deployment group create -g <rg> -f main.bicep -p ghcrImage=ghcr.io/<user>/previsor-imoveis-api:latest

param location string = resourceGroup().location
param baseName string = 'previmoveis'
param ghcrImage string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take('${baseName}st${uniqueString(resourceGroup().id)}', 24)
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

resource dadosContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storage.name}/default/dados'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${baseName}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${baseName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-api'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: ghcrImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8000 }
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0 // ESSENCIAL para custo zero — não mudar para 1
        maxReplicas: 1
      }
    }
  }
}

resource funcPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${baseName}-func-plan'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' } // Consumption: 1M execuções grátis/mês
}

resource scraper 'Microsoft.Web/sites@2023-12-01' = {
  name: '${baseName}-scraper'
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: funcPlan.id
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
  }
}

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output storageAccount string = storage.name
