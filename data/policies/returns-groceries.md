---
doc_id: returns-groceries
title: Groceries returns
version: 1
effective_date: 2026-01-01
---

# Groceries returns

Food and grocery items are perishable and cannot be resold once opened for hygiene reasons.

## 1. Non-returnable
Groceries, including rice, oil and dry fruits, are **non-returnable** for change of mind, taste or preference, and for items past expiry that were bought in error.

```rules
[{"rule_id": "GRO-NR", "kind": "not_returnable", "applies_to": {"category": "groceries"}, "window_days": null, "outcome": "not_returnable", "overrides": ["RET-GEN-30"], "requires_evidence": "none"}]
```

## 2. Damaged or expired on arrival
If a grocery item arrives damaged, leaking or already expired, the customer may report it within **48 hours** of delivery. The customer must upload clear photos of the item and the packaging. Once the photo check passes, the seller replaces the item. A refund applies only when a replacement is out of stock.

```rules
[{"rule_id": "GRO-DMG-48H", "kind": "exception", "applies_to": {"category": "groceries", "reported_within_hours": 48}, "window_days": null, "outcome": "replacement_only", "overrides": ["GRO-NR"], "requires_evidence": "photo"}]
```

## 3. Opened packs
Opened packs are not eligible after 48 hours, even if the customer believes the content is spoiled.
