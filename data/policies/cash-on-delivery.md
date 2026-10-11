---
doc_id: cash-on-delivery
title: Cash on delivery refunds
version: 1
effective_date: 2026-01-01
---

# Cash on delivery refunds

Orders paid on delivery cannot be refunded to a card, so refunds use bank transfer or store credit.

## 1. Refund method
For cash-on-delivery orders, the refund is sent by bank transfer. The customer provides an account in their own name, verified before the transfer. Store credit is offered as an alternative.

```rules
[{"rule_id": "COD-REF-BANK", "kind": "refund_method", "applies_to": {"payment_method": "cod"}, "window_days": null, "outcome": "return", "overrides": [], "requires_evidence": "none"}]
```

## 2. Timeline
Bank transfers are initiated within 7 days of the returned item being received, and reach the account within 3 to 5 business days.

## 3. Account details
Support never asks for card numbers, PINs or one-time passwords. Customers provide only the account holder name, account number and IFSC code through the secure refund form.
