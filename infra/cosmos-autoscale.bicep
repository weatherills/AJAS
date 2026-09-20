param primary string
param secondary string = ''
param autoscaleMaxRu int = 4000

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: 'ajas-cosmos'
  location: primary
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: true
    enableMultipleWriteLocations: false
    locations: empty(secondary) ? [
      { locationName: primary, failoverPriority: 0, isZoneRedundant: false }
    ] : [
      { locationName: primary, failoverPriority: 0, isZoneRedundant: false }
      { locationName: secondary, failoverPriority: 1, isZoneRedundant: false }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

resource sql 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmos
  name: 'ajas'
  properties: {
    resource: { id: 'ajas' }
  }
}

resource matchesAutoscale 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: sql
  name: 'matches'
  properties: {
    resource: {
      id: 'matches'
      partitionKey: { paths: ['/user_id'], kind: 'Hash' }
    }
    options: {
      autoscaleSettings: { maxThroughput: autoscaleMaxRu }
    }
  }
}
