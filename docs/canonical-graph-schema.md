# Canonical graph schema

The machine-readable contract is `schema/catalogue-schema.yaml`. This document
explains the topology it encodes.

## Core topology

An `Integration` is one hop between exactly two interfaces:

```text
(Application)-[:EXPOSES]->(Interface)-[:SOURCE_OF]->(Integration)
    -[:TARGETS]->(Interface)<-[:USES]-(Application)
```

Consecutive hops share an interface:

```text
(Interface)-[:SOURCE_OF]->(Integration)-[:TARGETS]->(Interface)
    -[:SOURCE_OF]->(Integration)-[:TARGETS]->(Interface)
```

An intermediate application may consume one interface and expose another:

```text
(Integration)-[:TARGETS]->(Interface)<-[:USES]-(Application)
    -[:EXPOSES]->(Interface)-[:SOURCE_OF]->(Integration)
```

Connectivity lives exclusively in relationships. An end-to-end flow is a path
between applications; it is not a node and is not created by `flow_id`,
`sequence`, names, or other properties.

## Platform identity

ServiceNow provisions APM IDs for business applications and integration
platforms. Therefore:

- `Application.apm_id` is the authoritative ServiceNow identifier.
- An integration platform is represented as an `Application` with
  `application_role: integration_platform` (or `both`).
- `Integration.platform_apm_id` references that application master record.
- `Platform` is not a canonical node and does not participate in E2E topology.

## Property policy

Each node type defines required and optional properties. Additional
source-specific properties are allowed when namespaced as
`x_<source>_<property>`, such as `x_kong_route_path`.

Neo4j properties must be scalar values or lists of scalar values. Nested source
objects must be normalized before loading or retained outside the graph as raw
extractor artifacts.

## Lifecycle statuses

The canonical values are:

```text
planned
active
deprecated
decommissioning
decommissioned
unknown
```

Discovery state is separate from lifecycle. A missing extractor observation
must not silently decommission an object.
