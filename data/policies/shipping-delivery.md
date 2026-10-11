---
doc_id: shipping-delivery
title: Shipping, delivery and delays
version: 1
effective_date: 2026-01-01
---

# Shipping, delivery and delays

## 1. Shipping fee
Orders of ₹499 or more ship free. Below that, a shipping fee of ₹49 applies.

## 2. Shipping fee refunds
The shipping fee is refunded only when the seller is at fault: a damaged, defective, wrong or missing item. It is not refunded for change of mind.

```rules
[{"rule_id": "SHIP-FEE-SELLER", "kind": "refund_method", "applies_to": {"item_condition": "damaged"}, "window_days": null, "outcome": "return", "overrides": [], "requires_evidence": "none"}]
```

## 3. Delivery timelines
Standard delivery takes 3 to 6 business days. The promised delivery date is shown on the order.

## 4. Delivery delays
If a delivery is more than 2 days past its promised date, the customer may ask for a status update. Support checks the carrier scan history and either gives a new date or offers a cancellation.
