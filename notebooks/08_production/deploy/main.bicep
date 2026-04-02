@description('The location for all resources')
param location string = resourceGroup().location

@description('The base name for resources')
param baseName string = 'travelagent'

@description('Environment (dev, staging, prod)')
param environment string = 'dev'

var uniqueSuffix = uniqueString(resourceGroup().id)
var resourceToken = '${baseName}${uniqueSuffix}'

// ==================== Azure OpenAI ====================

resource openAI 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: 'aoai-${resourceToken}'
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'aoai-${resourceToken}'
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAI
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAI
  name: 'text-embedding-ada-002'
  dependsOn: [gpt4Deployment]
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-ada-002'
      version: '2'
    }
  }
}

// ==================== Cosmos DB ====================

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-09-15' = {
  name: 'cosmos-${resourceToken}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-09-15' = {
  parent: cosmosAccount
  name: 'travel-memory'
  properties: {
    resource: {
      id: 'travel-memory'
    }
  }
}

resource memoriesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-09-15' = {
  parent: cosmosDatabase
  name: 'memories'
  properties: {
    resource: {
      id: 'memories'
      partitionKey: {
        paths: ['/employee_id']
        kind: 'Hash'
      }
    }
  }
}

resource requestsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-09-15' = {
  parent: cosmosDatabase
  name: 'travel-requests'
  properties: {
    resource: {
      id: 'travel-requests'
      partitionKey: {
        paths: ['/employee_id']
        kind: 'Hash'
      }
    }
  }
}

// ==================== Azure AI Search ====================

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: 'search-${resourceToken}'
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

// ==================== Redis Cache ====================

resource redisCache 'Microsoft.Cache/redis@2023-08-01' = {
  name: 'redis-${resourceToken}'
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

// ==================== Application Insights ====================

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'logs-${resourceToken}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${resourceToken}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ==================== Container Apps Environment ====================

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'cae-${resourceToken}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ==================== Container Registry ====================

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${uniqueSuffix}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ==================== Managed Identity ====================

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceToken}'
  location: location
}

// Role assignments for managed identity
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-09-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, managedIdentity.id, 'cosmos-data-contributor')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002' // Built-in Data Contributor
    principalId: managedIdentity.properties.principalId
    scope: cosmosAccount.id
  }
}

resource openAIRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAI.id, managedIdentity.id, 'cognitive-services-user')
  scope: openAI
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ==================== Container App ====================

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'ca-${resourceToken}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
        {
          name: 'azure-search-key'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'redis-password'
          value: redisCache.listKeys().primaryKey
        }
        {
          name: 'appinsights-cs'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'travel-agent'
          image: '${containerRegistry.properties.loginServer}/travel-agent:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: openAI.properties.endpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: 'gpt-4o'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosAccount.properties.documentEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: 'travel-memory'
            }
            {
              name: 'COSMOS_CONTAINER'
              value: 'memories'
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: 'https://${searchService.name}.search.windows.net'
            }
            {
              name: 'AZURE_SEARCH_ADMIN_KEY'
              secretRef: 'azure-search-key'
            }
            {
              name: 'AZURE_SEARCH_INDEX'
              value: 'travel-memories'
            }
            {
              name: 'REDIS_HOST'
              value: '${redisCache.name}.redis.cache.windows.net'
            }
            {
              name: 'REDIS_PORT'
              value: '6380'
            }
            {
              name: 'REDIS_PASSWORD'
              secretRef: 'redis-password'
            }
            {
              name: 'REDIS_SSL'
              value: 'true'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-cs'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentity.properties.clientId
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ==================== Outputs ====================

output AZURE_OPENAI_ENDPOINT string = openAI.properties.endpoint
output COSMOS_ENDPOINT string = cosmosAccount.properties.documentEndpoint
output AZURE_SEARCH_ENDPOINT string = 'https://${searchService.name}.search.windows.net'
output REDIS_HOST string = '${redisCache.name}.redis.cache.windows.net'
output CONTAINER_APP_URL string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.properties.clientId
output ACR_LOGIN_SERVER string = containerRegistry.properties.loginServer
