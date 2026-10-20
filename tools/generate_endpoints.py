"""Freeze endpoint metadata from the checked-in OpenAPI snapshot."""

import json
from pathlib import Path

from generate_wire import NAMES

ROOT = Path(__file__).resolve().parents[1]
IDS = [
    "profile",
    "balance",
    "deposit",
    "deposit_status",
    "blocked_titles",
    "inventory",
    "sync",
    "user_offers",
    "closed_offers",
    "target_depth",
    "aggregated_prices",
    "user_targets",
    "closed_targets",
    "create_targets",
    "delete_targets",
    "batch_create",
    "batch_update",
    "batch_delete",
    "market_offers",
    "buy",
    "withdraw",
    "fees",
    "last_sales",
]


def generate() -> str:
    spec = json.loads((ROOT / "contracts/openapi.json").read_text())
    operations = [
        (path, method, op)
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method in {"get", "post", "patch", "delete", "put"}
    ]
    assert len(operations) == len(IDS) == 23
    lines = [
        '"""Generated endpoint registry; run tools/generate_endpoints.py to regenerate."""',
        "from .endpoints_base import Endpoint",
        "from . import wire",
        "",
        "ENDPOINTS = {",
    ]
    manifest = {}
    for name, (path, method, op) in zip(IDS, operations, strict=True):
        response = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].rsplit(
            "/", 1
        )[-1]
        body = (
            op.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("$ref")
        )
        params = op.get("parameters", [])
        safe = method == "get" or name == "aggregated_prices"
        group = "sales" if name == "last_sales" else "other"
        body_expr = f"wire.{NAMES[body.rsplit('/', 1)[-1]]}" if body else "None"
        lines.append(
            f"    {name!r}: Endpoint(name={name!r}, method={method.upper()!r}, path={path!r}, response=wire.{NAMES[response]}, body={body_expr}, parameters={params!r}, safe_to_retry={safe!r}, group={group!r}),"
        )
        manifest[name] = {
            "method": method.upper(),
            "path": path,
            "safe_to_retry": safe,
            "response_schema": response,
        }
    lines.extend(["}", ""])
    (ROOT / "contracts/endpoints.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "src/dmarket_client/_internal/endpoints.py").write_text(generate())
