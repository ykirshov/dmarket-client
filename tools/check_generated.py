"""Fail when checked-in generated Python differs semantically from its sources."""

import ast
from pathlib import Path

import generate_async
import generate_endpoints
import generate_wire

ROOT = Path(__file__).resolve().parents[1]


def normalized(source: str) -> str:
    tree = ast.parse(source)
    imports, rest = [], []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Ruff may regroup or reorder imports. Compare individual imported names.
            for name in node.names:
                if isinstance(node, ast.ImportFrom):
                    imports.append((node.level, node.module or "", name.name, name.asname))
                else:
                    imports.append((0, "", name.name, name.asname))
        else:
            rest.append(node)
    tree.body = rest
    return repr(sorted(imports)) + ast.dump(tree, include_attributes=False)


if __name__ == "__main__":
    generators = {
        "_internal/wire.py": generate_wire.generate,
        "_internal/endpoints.py": generate_endpoints.generate,
        "async_resources.py": generate_async.generate,
    }
    for filename, generator in generators.items():
        actual = (ROOT / "src/dmarket_client" / filename).read_text()
        if normalized(actual) != normalized(generator()):
            raise SystemExit(f"Generated file is stale: {filename}")
    print("Generated wire models, endpoints and async resources are up to date")
