// M3: embeddings (L3g) on the existing Foundry account from M1, and the `shopsense`
// database (memory, policy rules) on the existing PostgreSQL server from M2.
// Deploy into the existing resource group:
//   az deployment group create -g rg-shopsense-dev-eus2 -f infra/m3/main.bicep

targetScope = 'resourceGroup'

@description('Existing Foundry (AIServices) account created in M1.')
param foundryAccountName string = 'ais-shopsense-dev-yuegx3'

@description('Existing PostgreSQL Flexible Server created in M2.')
param postgresServerName string = 'psql-shopsense-dev-yuegx3'

@description('Embedding capacity in thousands of tokens per minute (free-trial friendly).')
param embeddingCapacity int = 120

resource account 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' existing = {
  name: foundryAccountName
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: account
  name: 'text-embedding-3-small'
  sku: { name: 'Standard', capacity: embeddingCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'text-embedding-3-small', version: '1' }
  }
}

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresServerName
}

resource shopsenseDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: 'shopsense'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

output embeddingDeployment string = embedding.name
output shopsenseDatabase string = shopsenseDatabase.name
