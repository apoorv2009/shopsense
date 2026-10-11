// ShopSense M1 infrastructure: resource group + Foundry with Claude Opus 5.5 and an
// Azure OpenAI model (provider-agnostic client). Free-trial profile (D15), East US 2.
//
// IMPORTANT: deploying the Claude deployment accepts the Anthropic Marketplace offer
// terms via `modelProviderData`. Set the organisation fields to your real details.
targetScope = 'subscription'

@description('Environment name, e.g. dev.')
param environmentName string = 'dev'

@allowed(['eastus2', 'swedencentral', 'westus2'])
param location string = 'eastus2'

@description('Object id of the developer running the code locally (gets inference role).')
param principalId string = ''

param claudeModel string = 'claude-opus-5-5'
param claudeModelVersion string = '1'
@description('Tokens per minute / 1000. Keep low on a free trial.')
param claudeCapacity int = 25
param claudeOrganizationName string
@minLength(2)
@maxLength(2)
param claudeCountryCode string = 'IN'
@allowed(['technology', 'finance', 'healthcare', 'education', 'retail', 'manufacturing', 'government', 'media', 'other'])
param claudeIndustry string = 'education'

param openAiModel string = 'gpt-4.1-mini'
param openAiModelVersion string = '2025-04-14'
param openAiCapacity int = 10

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
    claudeModel: claudeModel
    claudeModelVersion: claudeModelVersion
    claudeCapacity: claudeCapacity
    claudeOrganizationName: claudeOrganizationName
    claudeCountryCode: claudeCountryCode
    claudeIndustry: claudeIndustry
    openAiModel: openAiModel
    openAiModelVersion: openAiModelVersion
    openAiCapacity: openAiCapacity
    principalId: principalId
  }
}

// Values for the repository .env (SHOPSENSE_* settings)
output SHOPSENSE_FOUNDRY_RESOURCE string = foundry.outputs.accountName
output SHOPSENSE_CLAUDE_DEPLOYMENT string = foundry.outputs.claudeDeployment
output SHOPSENSE_AZURE_OPENAI_ENDPOINT string = foundry.outputs.openAiEndpoint
output SHOPSENSE_AZURE_OPENAI_DEPLOYMENT string = foundry.outputs.openAiDeployment
output AZURE_RESOURCE_GROUP string = rg.name
