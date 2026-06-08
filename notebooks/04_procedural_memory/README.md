# Module 4: Procedural Memory

Procedural memory stores rules, policies, and procedures that guide agent behavior. It answers: *"How do I do this?"* and *"What are the rules?"*

## Learning Objectives

By the end of this module, you will:

1. Understand **procedural memory** and when to use it
2. Move instructions from hardcoded strings to version-controlled files
3. Implement a **feedback loop** for iterative prompt refinement
4. Build context-dependent procedures with **SKILL.md** files
5. Use a `SkillsProvider` for lazy-loading task-specific procedures

## Prerequisites

- Completed Modules 1–3
- Azure AI Foundry Project with model deployment (configured via `FOUNDRY_MODEL`)

## Time

~45 minutes

## Files in This Module

| File | Purpose |
|------|---------|
| `04_procedural_memory.ipynb` | Hands-on notebook with concepts |
| `prompts/v1.md` | Baseline instructions |
| `prompts/v2.md` | Instructions with trigger conditions |
| `prompts/v3.md` | Instructions with full procedures |
| `skills/domestic-booking/SKILL.md` | Domestic booking procedure + budget rules |
| `skills/international-booking/SKILL.md` | International booking procedure + visa checklist |

## Key Concepts

### Instructions Are Memory Too

Prompts and procedures are the agent's "muscle memory" — they define *how* it acts. Version-controlling them in `.md` files enables git-tracked iteration.

### The Feedback Loop

```
Run → Observe failure → Refine prompt → Verify fix → Commit
```

### Context-Dependent Procedures (Skills)

Instead of loading all procedures upfront, the `SkillsProvider` advertises available skills and loads them on demand:

```
skills/
├── domestic-booking/
│   ├── SKILL.md              # Procedure + decision logic
│   └── budget-limits.json    # Resource data
└── international-booking/
    ├── SKILL.md
    ├── budget-limits.json
    └── visa-checklist.md
```

### Storage Choice: Filesystem + Git

| Feature | Benefit |
|---------|---------|
| Version control | Track changes via git history |
| PR reviews | Team reviews prompt changes |
| Progressive disclosure | Load only what's needed |
| Human-readable | Markdown files anyone can edit |

## Quick Start

```bash
# Just run the notebook — no external services needed
jupyter notebook 04_procedural_memory.ipynb
```

## What You'll Build

An agent that:
- Loads instructions from versioned `.md` files
- Progressively improves through V1 → V2 → V3 iterations
- Uses SKILL.md files for task-specific procedures and budget rules

## Navigation

- ← Previous: [Module 3: Semantic Memory](../03_semantic_memory/)
- → Next: [Module 5: Combined Memory](../05_combined_memory/)
