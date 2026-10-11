---
doc_id: returns-apparel
title: Apparel and footwear returns
version: 1
effective_date: 2026-01-01
---

# Apparel and footwear returns

Apparel and footwear have a longer window to allow for fit issues.

## 1. Return window for apparel
Apparel, footwear and fashion accessories can be returned within **45 days** of delivery. The general 30-day window does not apply.

```rules
[{"rule_id": "APP-RET-45", "kind": "return_window", "applies_to": {"category": "apparel"}, "window_days": 45, "outcome": "return", "overrides": ["RET-GEN-30"], "requires_evidence": "none"}]
```

## 2. Condition
Items must be unworn, unwashed and with tags attached. Footwear must be returned in the original box with no sole wear. Innerwear and swimwear are non-returnable once the seal is broken.

## 3. Size exchange
A size exchange within the same window is free. The customer pays nothing for the exchange shipping if the item is returned as unworn.
