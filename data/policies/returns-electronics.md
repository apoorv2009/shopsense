---
doc_id: returns-electronics
title: Electronics addendum
version: 1
effective_date: 2026-01-01
---

# Electronics addendum

This addendum overrides the general return window for electronic products (phones, laptops, headphones, speakers, smartwatches, appliances) that are not accessories.

## 1. Return window for electronics
Electronics that are not accessories can be returned within **15 days** of delivery. Day 15 is the last accepted day; a return requested on day 16 is not eligible under this rule. The general 30-day window does not apply to these products.

```rules
[{"rule_id": "ELE-RET-15", "kind": "return_window", "applies_to": {"category": "electronics", "is_accessory": false}, "window_days": 15, "outcome": "return", "overrides": ["RET-GEN-30"], "requires_evidence": "none"}]
```

## 2. Condition
The product must be switched on only for setup, with seals and screen protectors intact, and without water damage. Opened software or activation keys are not returnable.

## 3. Warranty interaction
A return inside the window is a refund or replacement. After the window, faults are handled under the warranty policy.
