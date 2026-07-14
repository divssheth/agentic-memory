---
name: memory-identification
description: Criteria and scoring rubric for deciding what information to store in long-term memory versus discard after the conversation ends.
---

# Memory Identification Skill

## Purpose

Not every piece of information in a conversation should be stored. This skill
defines the criteria an agent uses to decide whether a statement, event, or
preference is worth promoting into long-term memory.

## Scoring Criteria (all scored 0–3)

| Criterion | 0 (Discard) | 1 (Weak) | 2 (Moderate) | 3 (Strong) |
|-----------|-------------|-----------|--------------|------------|
| **Durability** | Ephemeral fact ("today's weather") | Short-term plan ("next week") | Months-level ("this quarter") | Indefinite ("always prefer aisle seats") |
| **Reusability** | One-shot context | Rare re-use | Likely re-use across sessions | Used every interaction |
| **User-specificity** | Generic knowledge | Org-wide fact | Team/role specific | Unique to this user |
| **Actionability** | Cannot change agent behaviour | Mild influence | Changes recommendations | Directly gates a decision |

## Decision Rule

```
score = durability + reusability + user_specificity + actionability  (0–12)

if score >= 8:  → STORE (promote to candidate memory)
if score 5–7:   → MAYBE (store only if confirmed by user or repeated)
if score <= 4:  → DISCARD (do not memorise)
```

## Anti-Patterns (Never Memorise)

1. **Transient logistics** — "My meeting is at 3 PM today"
2. **Publicly available facts** — "The capital of France is Paris"
3. **Sensitive data without consent** — Credit card numbers, health info
4. **Unconfirmed speculation** — "I think maybe I like window seats?"
5. **Tool output verbatim** — Store the insight, not the raw JSON

## Good Memory Examples

| Statement | D | R | U | A | Score | Decision |
|-----------|---|---|---|---|-------|----------|
| "I always fly Delta when going to NYC" | 3 | 3 | 3 | 3 | 12 | STORE |
| "Book me on the 9 AM flight tomorrow" | 0 | 0 | 3 | 2 | 5 | MAYBE |
| "Marriott Midtown was noisy last trip — try somewhere else" | 2 | 2 | 3 | 3 | 10 | STORE |
| "What's the weather in Seattle?" | 0 | 0 | 0 | 0 | 0 | DISCARD |
| "My max budget is always $250/night for hotels" | 3 | 3 | 3 | 3 | 12 | STORE |
| "The Hilton lobby was renovated recently" | 1 | 1 | 0 | 1 | 3 | DISCARD |

## Integration

The agent should evaluate each user statement against these criteria *before*
calling `store_event`. If the score is below threshold, the information is used
in the current conversation only and not persisted.
