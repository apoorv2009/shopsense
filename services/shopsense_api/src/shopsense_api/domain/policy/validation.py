"""Load-time consistency checks (LLD-6 L6g): rule values must appear in their section's text,
conditions must be known, rule IDs unique, overrides must resolve.

Precedence ties are detected at M4 with the rules engine (see plans/m3.md, deferred)."""

from collections.abc import Sequence

from shopsense_api.domain.policy.model import PolicyDocument, PolicyRule, PolicySection

KNOWN_CONDITIONS = frozenset(
    {
        "category",
        "is_accessory",
        "item_condition",
        "price_below_paise",
        "reported_within_hours",
        "payment_method",
    }
)


class PolicyLoadError(ValueError):
    """Raised when the policy corpus is inconsistent; loading fails closed."""


def validate_corpus(docs: Sequence[PolicyDocument]) -> None:
    rules = [(doc, sec, rule) for doc in docs for sec in doc.sections for rule in sec.rules]
    ids = [rule.rule_id for _, _, rule in rules]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise PolicyLoadError(f"duplicate rule IDs: {duplicates}")
    known = set(ids)
    for _, sec, rule in rules:
        _check_rule(rule, sec)
        missing = [o for o in rule.overrides if o not in known]
        if missing:
            raise PolicyLoadError(f"{rule.rule_id} overrides unknown rules {missing}")


def _check_rule(rule: PolicyRule, section: PolicySection) -> None:
    unknown = sorted(set(rule.applies_to) - KNOWN_CONDITIONS)
    if unknown:
        raise PolicyLoadError(f"{rule.rule_id} uses unknown conditions {unknown}")
    if rule.window_days is not None and f"{rule.window_days} day" not in section.text:
        raise PolicyLoadError(f"{rule.rule_id}: {rule.window_days} days not in section text")
    hours = rule.applies_to.get("reported_within_hours")
    if hours is not None and f"{hours} hours" not in section.text:
        raise PolicyLoadError(f"{rule.rule_id}: {hours} hours not in section text")
