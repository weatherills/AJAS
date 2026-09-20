targetScope = resourceGroup()

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'ajas${uniqueString(resourceGroup().id)}'
  location: resourceGroup().location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: 'ajas-cosmos'
  location: resourceGroup().location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [{ locationName: resourceGroup().location, failoverPriority: 0 }]
    capabilities: [{ name: 'EnableServerless' }]
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmos
  name: 'ajas'
  properties: {
    resource: { id: 'ajas' }
  }
}

output resources array = [
  'functionApp'
  'cosmos'
  'storage'
  'keyVault'
  'containerApp'
]
