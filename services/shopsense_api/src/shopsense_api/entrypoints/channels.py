"""Channel helpers shared by the API and the parity evaluation (registered senders, D8d)."""

import json
from pathlib import Path

from shopsense_api.entrypoints.settings import REPO_ROOT

SENDERS_FILE = REPO_ROOT / "data" / "registered_senders.json"


def normalise_address(address: str) -> str:
    return address.strip().lower()


def load_senders(path: Path = SENDERS_FILE) -> dict[str, str]:
    """Registered sender address -> customer number. Unregistered senders get no processing."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {normalise_address(row["email"]): row["customer_no"] for row in data["senders"]}
