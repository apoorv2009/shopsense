---
doc_id: refund-methods
title: Refund methods and timelines
version: 1
effective_date: 2026-01-01
---

# Refund methods and timelines

## 1. Original payment method
Refunds for prepaid orders (UPI, credit card, debit card, net banking) go back to the original payment method.

```rules
[{"rule_id": "REF-ORIG", "kind": "refund_method", "applies_to": {"payment_method": "prepaid"}, "window_days": null, "outcome": "return", "overrides": [], "requires_evidence": "none"}]
```

## 2. Timeline
A refund is initiated within **7 days** of the returned item being received at our warehouse. Card and bank credits appear within 5 to 7 further business days, depending on the bank.

```rules
[{"rule_id": "REF-TIME-7", "kind": "refund_timeline", "applies_to": {}, "window_days": 7, "outcome": "return", "overrides": [], "requires_evidence": "none"}]
```

## 3. Refunds above the approval cap
Refunds above ₹5,000 are reviewed by a support specialist before they are released. The customer receives a reply within 2 business days.
