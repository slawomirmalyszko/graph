// Canonical uniqueness constraints. Safe to run repeatedly on Neo4j AuraDB.
CREATE CONSTRAINT application_id_unique IF NOT EXISTS
FOR (node:Application) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT application_apm_id_unique IF NOT EXISTS
FOR (node:Application) REQUIRE node.apm_id IS UNIQUE;

CREATE CONSTRAINT interface_id_unique IF NOT EXISTS
FOR (node:Interface) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT integration_id_unique IF NOT EXISTS
FOR (node:Integration) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT information_object_id_unique IF NOT EXISTS
FOR (node:InformationObject) REQUIRE node.id IS UNIQUE;

// Search indexes used by discovery queries and future NL-to-Cypher prompts.
CREATE INDEX application_name IF NOT EXISTS
FOR (node:Application) ON (node.name);

CREATE INDEX application_status IF NOT EXISTS
FOR (node:Application) ON (node.status);

CREATE INDEX interface_name IF NOT EXISTS
FOR (node:Interface) ON (node.name);

CREATE INDEX interface_status IF NOT EXISTS
FOR (node:Interface) ON (node.status);

CREATE INDEX integration_name IF NOT EXISTS
FOR (node:Integration) ON (node.name);

CREATE INDEX integration_status IF NOT EXISTS
FOR (node:Integration) ON (node.status);

CREATE INDEX integration_platform_apm_id IF NOT EXISTS
FOR (node:Integration) ON (node.platform_apm_id);

CREATE INDEX information_object_name IF NOT EXISTS
FOR (node:InformationObject) ON (node.name);

