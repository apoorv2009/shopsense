// ShopSense M2 infrastructure: Azure Database for PostgreSQL Flexible Server (B1ms,
// free-trial profile D15) with Entra-only authentication (no passwords, L9e) and the
// order_platform database. Deploys into the M1 resource group.
targetScope = 'subscription'

param environmentName string = 'dev'
param location string = 'eastus2'

@description('Object id of the developer (Entra administrator of the server).')
param principalId string

@description('User principal name of the developer, e.g. from az ad signed-in-user show.')
param principalName string

@description('Public IP of the developer machine allowed through the firewall.')
param clientIp string

var regionCode = location == 'eastus2' ? 'eus2' : location == 'swedencentral' ? 'sdc' : 'wus2'
var suffix = take(uniqueString(subscription().id, environmentName), 6)

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' existing = {
  name: 'rg-shopsense-${environmentName}-${regionCode}'
}

module postgres 'postgres.bicep' = {
  name: 'shopsense-postgres'
  scope: rg
  params: {
    location: location
    serverName: 'psql-shopsense-${environmentName}-${suffix}'
    tags: { project: 'shopsense', env: environmentName, purpose: 'learning', milestone: 'm2' }
    principalId: principalId
    principalName: principalName
    clientIp: clientIp
  }
}

output ORDER_PLATFORM_DB_HOST string = postgres.outputs.host
output ORDER_PLATFORM_DB_NAME string = postgres.outputs.database
