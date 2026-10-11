---
doc_id: returns-beauty
title: Beauty and personal care returns
version: 1
effective_date: 2026-01-01
---

# Beauty and personal care returns

Beauty and personal-care products carry hygiene restrictions.

## 1. Unopened products
Unopened beauty products can be returned within **7 days** of delivery.

```rules
[{"rule_id": "BEA-RET-7", "kind": "return_window", "applies_to": {"category": "beauty", "item_condition": "unopened"}, "window_days": 7, "outcome": "return", "overrides": ["RET-GEN-30"], "requires_evidence": "none"}]
```

## 2. Opened products
Opened or used beauty products are **non-returnable** for hygiene reasons, unless they are faulty or the seal was broken before delivery.

```rules
[{"rule_id": "BEA-OPEN-NR", "kind": "not_returnable", "applies_to": {"category": "beauty", "item_condition": "opened"}, "window_days": null, "outcome": "not_returnable", "overrides": ["RET-GEN-30"], "requires_evidence": "none"}]
```

## 3. Hair dryers
Hair dryers follow the electronics rules for faults and the unopened rule for change of mind.
