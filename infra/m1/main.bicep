// ShopSense M1 infrastructure: resource group + Foundry with two model vendors for the
// provider-agnostic client (OpenAI gpt-4.1-mini, Mistral AI mistral-medium) and an optional
// Claude deployment. Free-trial profile (D15), East US 2.
//
// IMPORTANT: deployClaude=true accepts the Anthropic Marketplace offer
// terms via `modelProviderData`. Set the organisation fields to your real details.
targetScope = 'subscription'

@description('Environment name, e.g. dev.')
param environmentName string = 'dev'

@allowed(['eastus2', 'swedencentral', 'westus2'])
param location string = 'eastus2'

@description('Object id of the developer running the code locally (gets inference role).')
param principalId string = ''

@description('Deploy Claude on Foundry. Requires Claude quota (free-trial subscriptions have none).')
param deployClaude bool = false
param claudeModel string = 'claude-opus-5-5'
param claudeModelVersion string = '1'
@description('Tokens per minute / 1000. Keep low on a free trial.')
param claudeCapacity int = 25
param claudeOrganizationName string = ''
@minLength(2)
@maxLength(2)
param claudeCountryCode string = 'IN'
@allowed(['technology', 'finance', 'healthcare', 'education', 'retail', 'manufacturing', 'government', 'media', 'other'])
param claudeIndustry string = 'education'

param openAiModel string = 'gpt-4.1-mini'
param openAiModelVersion string = '2025-04-14'
param openAiCapacity int = 10

param secondModel string = 'mistral-medium-2505'
param secondModelFormat string = 'Mistral AI'
param secondModelVersion string = '1'
param secondCapacity int = 10

var regionCode = location == 'eastus2' ? 'eus2' : location == 'swedencentral' ? 'sdc' : 'wus2'
var suffix = take(uniqueString(subscription().id, environmentName), 6)
var tags = {
  project: 'shopsense'
  env: environmentName
  purpose: 'learning'
  milestone: 'm1'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-shopsense-${environmentName}-${regionCode}'
  location: location
  tags: tags
}

module foundry 'foundry.bicep' = {
  name: 'shopsense-foundry'
  scope: rg
  params: {
    location: location
    tags: tags
    accountName: 'ais-shopsense-${environmentName}-${suffix}'
    projectName: 'proj-shopsense-${environmentName}'
    deployClaude: deployClaude
    claudeModel: claudeModel
    claudeModelVersion: claudeModelVersion
    claudeCapacity: claudeCapacity
    claudeOrganizationName: claudeOrganizationName
    claudeCountryCode: claudeCountryCode
    claudeIndustry: claudeIndustry
    openAiModel: openAiModel
    openAiModelVersion: openAiModelVersion
    openAiCapacity: openAiCapacity
    secondModel: secondModel
    secondModelFormat: secondModelFormat
    secondModelVersion: secondModelVersion
    secondCapacity: secondCapacity
    principalId: principalId
  }
}

// Values for the repository .env (SHOPSENSE_* settings)
output SHOPSENSE_FOUNDRY_RESOURCE string = foundry.outputs.accountName
output SHOPSENSE_PRIMARY_DEPLOYMENT string = foundry.outputs.openAiDeployment
output SHOPSENSE_SECOND_VENDOR_DEPLOYMENT string = foundry.outputs.secondDeployment
output SHOPSENSE_CLAUDE_DEPLOYMENT string = foundry.outputs.claudeDeployment
output AZURE_RESOURCE_GROUP string = rg.name
