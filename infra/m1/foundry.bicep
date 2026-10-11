// M1: Foundry account + project + model deployments: primary (OpenAI), second vendor
// (Mistral AI), optional Claude (needs Claude quota)
// + least-privilege inference role for the developer (Entra auth, no keys).
// Schema follows the Azure-Samples Claude-on-Foundry starter kit.
param location string
param tags object
param accountName string
param projectName string

param deployClaude bool
param claudeModel string
param claudeModelVersion string
param claudeCapacity int
param claudeOrganizationName string
param claudeCountryCode string
param claudeIndustry string

param openAiModel string
param openAiModelVersion string
param openAiCapacity int

param secondModel string
param secondModelFormat string
param secondModelVersion string
param secondCapacity int

param principalId string

// Cognitive Services User: inference data actions only
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource account 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: accountName
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true // Entra only (L9e)
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

resource developerInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(account.id, principalId, cognitiveServicesUserRoleId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: principalId
    principalType: 'User'
  }
}

resource claude 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = if (deployClaude) {
  parent: account
  name: claudeModel
  sku: { name: 'GlobalStandard', capacity: claudeCapacity }
  properties: {
    model: { format: 'Anthropic', name: claudeModel, version: claudeModelVersion }
    modelProviderData: {
      organizationName: claudeOrganizationName
      countryCode: claudeCountryCode
      industry: claudeIndustry
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [project, developerInference]
}

// Deployments under one account are serialised to avoid 409s
resource openAi 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: account
  name: openAiModel
  sku: { name: 'GlobalStandard', capacity: openAiCapacity }
  properties: {
    model: { format: 'OpenAI', name: openAiModel, version: openAiModelVersion }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [project, claude]
}

resource secondVendor 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: account
  name: secondModel
  sku: { name: 'GlobalStandard', capacity: secondCapacity }
  properties: {
    model: { format: secondModelFormat, name: secondModel, version: secondModelVersion }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [openAi]
}

output accountName string = account.name
output claudeDeployment string = deployClaude ? claudeModel : ''
output openAiDeployment string = openAi.name
output secondDeployment string = secondVendor.name
