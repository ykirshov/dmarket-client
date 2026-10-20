"""Generate native async resource methods from the sync resource definitions."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AsyncResources(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in {"SyncResource", "Iterator"}:
            node.id = {"SyncResource": "AsyncResource", "Iterator": "AsyncIterator"}[node.id]
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        for alias in node.names:
            if alias.name in {"SyncResource", "Iterator"}:
                alias.name = {"SyncResource": "AsyncResource", "Iterator": "AsyncIterator"}[
                    alias.name
                ]
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {
                "_execute",
                "batch_create",
                "batch_update",
                "batch_delete",
                "list_reduced",
            }:
                return ast.Await(value=node)
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "time"
                and node.func.attr == "sleep"
            ):
                node.func.value.id = "asyncio"
                return ast.Await(value=node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
        self.generic_visit(node)
        if node.name.startswith("iter_"):
            return node
        return ast.AsyncFunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=node.type_comment,
            type_params=node.type_params,
        )


def generate() -> str:
    tree = ast.parse((ROOT / "src/dmarket_client/resources.py").read_text())
    tree = AsyncResources().visit(tree)
    tree.body.insert(1, ast.Import(names=[ast.alias(name="asyncio")]))
    tree.body[0] = ast.Expr(
        value=ast.Constant(
            value="Generated native async resources; edit resources.py and run tools/generate_async.py."
        )
    )
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


if __name__ == "__main__":
    (ROOT / "src/dmarket_client/async_resources.py").write_text(generate())
