param location string
param serverName string
param tags object
param principalId string
param principalName string
param clientIp string

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenant().tenantId
    }
  }
}

resource admin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: server
  name: principalId
  properties: {
    principalType: 'User'
    principalName: principalName
    tenantId: tenant().tenantId
  }
}

resource devMachine 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: server
  name: 'developer-machine'
  properties: { startIpAddress: clientIp, endIpAddress: clientIp }
  dependsOn: [admin]
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: 'order_platform'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
  dependsOn: [devMachine]
}

output host string = server.properties.fullyQualifiedDomainName
output database string = database.name
