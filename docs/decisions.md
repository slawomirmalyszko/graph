# Architecture decisions and open questions

This lightweight log records decisions made before formal ADRs are warranted.

## Accepted

### AWS home region

The project uses Europe (Stockholm), `eu-north-1`, as its AWS home region.
The new AWS experience assigns European Free Plan projects to this region and
does not allow their project region to be changed. Region-dependent service and
Bedrock model availability must still be verified before implementation.

### Core graph path

An end-to-end flow starts and ends at an `Application` and can traverse other
applications:

```text
(Application)-[:EXPOSES]->(Interface)-[:SOURCE_OF]->(Integration)
  -[:TARGETS]->(Interface)<-[:USES]-(Application)
```

Consecutive integration hops connect through shared Interface nodes. An
end-to-end flow is a traversed path between Application nodes; `flow_id` and
`sequence` properties do not create topology.

### Core node concepts

- `Application`
- `Interface`
- `Integration`
- `InformationObject`

`Interface` abstracts technology-specific concepts such as APIs, events, topics,
queues, and file endpoints. A defined type property and/or additional labels will
retain their concrete meaning.

An `Integration` connects exactly two interfaces: one incoming `SOURCE_OF` and
one outgoing `TARGETS`. Applications, interfaces, and information objects may
participate in multiple relationships.

### Application minimum attributes

- `apm_id`
- `name`
- `status`: one of `planned`, `active`, `deprecated`, `decommissioning`,
  `decommissioned`, or `unknown`

### Canonical property policy

Each canonical node type will define:

- Required properties.
- Optional but formally defined properties.
- Additional source-specific properties.

Additional source properties use `x_<source>_<property>` names and must contain
Neo4j-compatible scalar values or lists of scalar values. The complete contract
is defined in `schema/catalogue-schema.yaml`.

### Platform representation

Platform is metadata on an Integration, represented by required
`platform_apm_id`. It references the ServiceNow APM ID of an Application master
record whose role is `integration_platform` or `both`. Platform is not a graph
node and does not participate in end-to-end topology.

### Query approach

The first version uses focused natural-language-to-Cypher generation rather than
a general autonomous agent. Prompts include selected schema context, worked
NL-to-Cypher examples, and initially a bounded application list or lookup context.

## Open

### Identity resolution

Automatic matching will use deterministic and later probabilistic evidence.
Unresolved mappings require human review. Git is the system of record for
reviewed rules and mappings; the graph contains their projected relationships.

The mapping file format, confidence model, and review workflow remain open.

### Information-object evidence

Define which evidence establishes that an interface or integration carries an
information object: naming, tags, descriptions, message schemas, manual mapping,
or semantic inference.
