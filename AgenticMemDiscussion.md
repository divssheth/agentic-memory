# Agentic Memory Requirements Document (Draft v0.1)

## 1. Purpose

Design an enterprise-grade Agentic Memory Framework that enables AI agents to:

* Learn and maintain long-term user-specific knowledge.
* Evolve knowledge over time.
* Resolve contradictions and uncertainty.
* Operate securely and responsibly.
* Provide transparency, auditability, and user control.
* Resist memory poisoning and memory-based attacks.
* Scale to enterprise workloads.

This framework should support multiple memory types and not assume a single storage or modelling paradigm.

# 2. Problem Statement

Current memory implementations are largely focused on:

* Information retrieval.
* Conversation recall.
* Task execution.
* Multi-agent orchestration.

However, they do not adequately address:

* Contradictory user information.
* Memory governance.
* Memory lifecycle management.
* User oversight and correction.
* Security and Responsible AI controls.
* Confidence in stored memories.
* Benchmarking and evaluation methodologies.

The team identified these as the key research and engineering gaps for Agentic Memory systems.

# 3. Vision

An Agent should behave more like a human assistant:

* Learn gradually.
* Maintain confidence levels.
* Reassess beliefs.
* Ask clarifying questions.
* Explain why something is stored.
* Allow user correction.
* Track memory evolution through time.

The memory system becomes a governed knowledge layer rather than a passive storage mechanism.

# 4. Memory Categories

The discussion identified multiple memory classes that require different handling mechanisms.

## FR-001 Semantic Memory

Capture durable facts about users, entities, and relationships.

Examples:

* User preferences
* Organisational relationships
* Skills
* Interests
* Locations

Potential representations:

* Ontologies
* Knowledge graphs
* Semantic networks

Semantic memory was identified as the most challenging memory class.

## FR-002 Episodic Memory

Capture historical events and interactions.

Examples:

* Conversations
* Decisions
* Meetings
* User activities

Potential representations:

* Event stores
* Cosmos DB
* Temporal databases



## FR-003 Procedural Memory

Capture learning about how an agent performs work.

Examples:

* Successful execution patterns
* Task strategies
* Agent self-improvement

Potential representations:

* Reinforcement learning signals
* Feedback loops
* Behavioural histories



# 5. Core Functional Requirements

## FR-004 Memory Identification

The system shall define explicit criteria determining:

* What qualifies as memory.
* What should not be memorised.
* Which information is transient.
* Which information is durable.

The team repeatedly highlighted this as the first architectural question.

## FR-005 Memory Lifecycle Management

The system shall support:

* Creation
* Validation
* Promotion
* Update
* Deprecation
* Deletion

of memory objects.

## FR-006 Memory Confidence Scoring

Every memory item shall contain a confidence score.

Possible confidence inputs:

* User assertion
* Enterprise data source
* Web source
* Knowledge base source
* Observation history
* Frequency of confirmation

Suggested examples were repeatedly discussed throughout the meeting.

## FR-007 Staged Memory Promotion

New memory should enter a provisional state before becoming trusted memory.

Example:

1. User says:
   * "I am vegetarian."

2. Agent stores:
   * Candidate memory.

3. Future interactions confirm claim.

4. Memory promoted to trusted state.

This was identified as an important defence against memory poisoning.

## FR-008 User Validation Loop

The system shall be able to:

* Ask clarifying questions.
* Confirm contradictions.
* Verify uncertainties.
* Request user corrections.

Example:

"You previously stated your home location was UK. Are you now located in India permanently or temporarily?"



## FR-009 Memory Update Mechanism

The system shall support belief revision rather than simple overwrite.

Example:

Old belief:

* User lives in New York.

New signal:

* User appears to live in Paris.

The system should reconcile and evolve the memory rather than creating duplicate truths.

This was described as a broader requirement than simple conflict resolution.

# 6. Governance Requirements

## FR-010 Contradiction Management

The system shall detect:

* Logical conflicts.
* Conflicting preferences.
* Changing beliefs.
* Incompatible facts.

Example:

* User believes X.
* User explicitly rejects X later.

The memory system must reconcile these states.

## FR-011 Memory Governance Layer

The system shall maintain governance controls over:

* Memory creation.
* Memory modification.
* Memory deletion.
* Memory promotion.

Governance was repeatedly identified as a central objective of the project.

## FR-012 User Control

Users shall be able to:

* Inspect memories.
* Modify memories.
* Approve memories.
* Delete memories.

The discussion highlighted user intervention as a key recommendation.

# 7. Security Requirements

## FR-013 Memory Audit Trail

The system shall record:

* Why memory was created.
* Who created it.
* When it was created.
* Source interaction.
* Modification history.

Example:

Why does the system believe:
"Emma is vegetarian?"

The audit trail must answer this question.

## FR-014 Memory Provenance

Every memory shall maintain provenance metadata.

Sources may include:

* User input
* Enterprise knowledge
* Web knowledge
* LLM-generated inferences



## FR-015 Least Privilege Memory Access

Memory access controls shall support:

* User-level access
* Agent-level access
* Data classification controls
* Sensitive memory protection

This was raised by [Akriti Mehta](https://www.office.com/search?q=Akriti+Mehta\&EntityRepresentationId=92f6a7e0-a712-4ba4-b0eb-6c4db36af0ca) during the governance discussion.

## FR-016 Cross-User Isolation

The system shall prevent:

* User memory leakage
* Cross-user contamination
* Unauthorised memory sharing

Explicitly identified as a major concern.

## FR-017 Memory Poisoning Detection

The framework shall detect suspicious memory changes.

Potential indicators:

* Large confidence changes.
* Unsupported beliefs.
* Low-connectivity graph nodes.
* Contradictory information.



# 8. Responsible AI Requirements

## FR-018 Sensitive Data Classification

The system shall classify memory according to:

* Personal data
* Sensitive personal data
* Behavioural preferences
* Protected information

The discussion emphasised that personalisation increasingly enters the realm of sensitive data management.

## FR-019 Persistence Policies

Memory shall support configurable persistence levels.

Examples:

* Session only
* Temporary
* Long-term
* Permanent

Memory tags were suggested as a mechanism for persistence management.

# 9. Architecture Requirements

## FR-020 Support Multiple Representations

Memory architecture shall support:

* Ontologies
* Knowledge graphs
* Relational structures
* Key-value stores
* Event stores

The team agreed no single storage model is suitable for all memory classes.

## FR-021 Entity Resolution

The system shall maintain a single canonical entity definition.

Example:

Emma = One Entity

Multiple relationships:

* Works at Microsoft
* Part of NTO
* Vegetarian

but not multiple duplicated Emma entities.



# 10. Evaluation Requirements

## FR-022 Agentic Memory Benchmark

The project requires a new benchmark for evaluating:

* Memory quality
* Memory accuracy
* Governance effectiveness
* Belief updates
* Contradiction handling
* Security resilience

The absence of suitable benchmarks was highlighted multiple times.

## FR-023 Confidence Measurement

The system shall provide measurable confidence in:

* Stored memory.
* Retrieved memory.
* Memory updates.
* User profile accuracy.

The team repeatedly noted the need for a stronger metric than "LLM as Judge."

# 11. Proposed Research Workstreams

Based on the discussion, I would structure the initiative into six parallel workstreams:

### Workstream 1 – Memory Taxonomy

* Define memory classes
* Define memory boundaries
* Define retention rules

### Workstream 2 – Memory Architecture

* Ontologies
* Knowledge graphs
* Semantic memory implementation
* Entity resolution

### Workstream 3 – Governance & Control

* User oversight
* Memory operations
* Contradiction handling

### Workstream 4 – Security & Responsible AI

* Audit
* Provenance
* Sensitive information
* DPIA alignment
* Policy enforcement

### Workstream 5 – Evaluation & Benchmarking

* Metrics
* Benchmarks
* Quality scoring

### Workstream 6 – Reference Implementation

* End-to-end use case
* Validation environment
* Production-scale architecture

# Recommended North Star Deliverable

The transcript naturally converges on a single research question:

> **How can enterprise AI agents maintain long-term memory that is accurate, auditable, secure, governable, user-controllable, and resilient to memory poisoning while continuously adapting to changing user beliefs and preferences?**
