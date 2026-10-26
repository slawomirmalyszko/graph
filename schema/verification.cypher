// 1. Catalogue counts by canonical node label.
MATCH (node)
WHERE any(label IN labels(node) WHERE label IN
  ['Application', 'Interface', 'Integration', 'InformationObject'])
UNWIND labels(node) AS label
WITH label, count(*) AS count
WHERE label IN ['Application', 'Interface', 'Integration', 'InformationObject']
RETURN label, count
ORDER BY label;

// 2. Every integration must have exactly one source and one target interface.
MATCH (integration:Integration)
OPTIONAL MATCH (source:Interface)-[:SOURCE_OF]->(integration)
WITH integration, count(source) AS source_count
OPTIONAL MATCH (integration)-[:TARGETS]->(target:Interface)
WITH integration, source_count, count(target) AS target_count
WHERE source_count <> 1 OR target_count <> 1
RETURN integration.id AS invalid_integration, source_count, target_count;

// 3. Every platform reference must resolve to an integration-platform application.
MATCH (integration:Integration)
OPTIONAL MATCH (platform:Application {apm_id: integration.platform_apm_id})
WHERE platform IS NULL
   OR NOT platform.application_role IN ['integration_platform', 'both']
RETURN integration.id AS invalid_integration, integration.platform_apm_id AS platform_apm_id;

// 4. Business objects matching "Order" and the integration hops carrying them.
MATCH (integration:Integration)-[:CARRIES]->(object:InformationObject)
WHERE toLower(object.name) CONTAINS 'order'
   OR any(alias IN coalesce(object.aliases, []) WHERE toLower(alias) CONTAINS 'order')
RETURN object.name AS information_object, integration.name AS integration,
       integration.platform_apm_id AS platform_apm_id
ORDER BY information_object, integration;

// 5. E2E application paths that interface with SAP S/4HANA.
MATCH path = (start:Application)-[:EXPOSES|USES|SOURCE_OF|TARGETS*1..20]-(sap:Application)
WHERE sap.name CONTAINS 'SAP'
  AND start <> sap
  AND all(node IN nodes(path) WHERE single(other IN nodes(path) WHERE other = node))
RETURN start.name AS start_application, sap.name AS sap_application,
       [node IN nodes(path) | coalesce(node.name, node.id)] AS path
ORDER BY start_application;

// 6. A readable directed E2E path between Salesforce and SAP.
MATCH path = (source:Application {name: 'Salesforce CRM'})
  -[:EXPOSES]->(:Interface)
  -[:SOURCE_OF|TARGETS*1..30]->(:Interface)
  <-[:USES]-(target:Application {name: 'SAP S/4HANA'})
RETURN path
LIMIT 10;

