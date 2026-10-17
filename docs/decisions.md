# Architecture decisions and open questions

This lightweight log records decisions made before formal ADRs are warranted.

## Accepted

### Core graph path

An end-to-end flow starts and ends at an `Application` and can traverse other
applications:

```text
(Application)-[:HAS_INTERFACE]->(Interface)
  <-[:SOURCE_INTERFACE]-(Integration)-[:TARGET_INTERFACE]->(Interface)
  <-[:HAS_INTERFACE]-(Application)
```

The exact relationship names and direction remain subject to schema design.

### Core node concepts

- `Application`
- `Interface`
- `Integration`
- `InformationObject`

`Interface` abstracts technology-specific concepts such as APIs, events, topics,
queues, and file endpoints. A defined type property and/or additional labels will
retain their concrete meaning.

An `Integration` connects exactly two interfaces. Applications, interfaces, and
information objects may participate in multiple relationships.

### Application minimum attributes

- `apm_id`
- `name`
- `status`: initially `live`, `to_be_decommissioned`, or `decommissioned`

### Canonical property policy

Each canonical node type will define:

- Required properties.
- Optional but formally defined properties.
- Additional source-specific properties.

The policy for validating, naming, and storing additional properties is still to
be designed.

### Query approach

The first version uses focused natural-language-to-Cypher generation rather than
a general autonomous agent. Prompts include selected schema context, worked
NL-to-Cypher examples, and initially a bounded application list or lookup context.

## Open

### Platform representation

Decide whether `Platform` is:

- A separate node related to interfaces/integrations.
- A property of an integration or interface.
- A hybrid: normalized platform node plus denormalized source properties.

This needs use-case-driven analysis before selection.

### Identity resolution

Automatic matching will use deterministic and later probabilistic evidence.
Unresolved mappings require human review. Git is the system of record for
reviewed rules and mappings; the graph contains their projected relationships.

The mapping file format, confidence model, and review workflow remain open.

### Information-object evidence

Define which evidence establishes that an interface or integration carries an
information object: naming, tags, descriptions, message schemas, manual mapping,
or semantic inference.

### Graph invariants

Define constraints and ingestion validation for the rule that every Integration
connects exactly two interfaces, including whether source and target direction is
mandatory and how bidirectional exchanges are represented.
