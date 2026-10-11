---
doc_id: order-cancellation
title: Order cancellation
version: 1
effective_date: 2026-01-01
---

# Order cancellation

## 1. Before dispatch
An order can be cancelled for a full refund at any time before it is dispatched.

```rules
[{"rule_id": "CAN-PRE-DISPATCH", "kind": "cancellation", "applies_to": {}, "window_days": null, "outcome": "return", "overrides": [], "requires_evidence": "none"}]
```

## 2. After dispatch
Once the order has been dispatched, it cannot be cancelled. The customer can refuse the delivery or return the item under the return policy for its category.

## 3. Refund for cancelled orders
A cancelled prepaid order is refunded to the original payment method in full, including the shipping fee.
