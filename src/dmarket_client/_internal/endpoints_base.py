import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import ValidationError

from ..exceptions import RequestValidationError
from .serialization import encode_json
from .wire_base import WireModel


def parameter_value(value: Any, schema: dict[str, Any], name: str) -> Any:
    kind = schema.get("type", "string")
    if kind == "array":
        if not isinstance(value, (tuple, list)):
            raise RequestValidationError(f"{name} must be a sequence")
        return [parameter_value(x, schema["items"], name) for x in value]
    if kind == "boolean":
        if not isinstance(value, bool):
            raise RequestValidationError(f"{name} must be boolean")
        return "true" if value else "false"
    if kind == "integer" or schema.get("format") in {"int64", "uint64"}:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise RequestValidationError(f"{name} must be an integer")
        if isinstance(value, str) and not re.fullmatch(r"-?\d+", value):
            raise RequestValidationError(f"{name} must be an integer")
        number = int(value)
        lo = 0 if schema.get("format") == "uint64" else -(2**63)
        hi = 2**64 - 1 if schema.get("format") == "uint64" else 2**63 - 1
        if not max(lo, schema.get("minimum", lo)) <= number <= min(hi, schema.get("maximum", hi)):
            raise RequestValidationError(f"{name} is outside its allowed range")
        return str(number)
    if not isinstance(value, str):
        raise RequestValidationError(f"{name} must be a string")
    if "enum" in schema and value not in schema["enum"]:
        raise RequestValidationError(f"{name} is not an allowed value")
    if len(value) > schema.get("maxLength", len(value)):
        raise RequestValidationError(f"{name} exceeds its maximum length")
    if len(value) < schema.get("minLength", 0):
        raise RequestValidationError(f"{name} is shorter than its minimum length")
    if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
        raise RequestValidationError(f"{name} does not match its required format")
    return value


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    path: str
    response: type[WireModel]
    body: type[WireModel] | None
    parameters: list[dict[str, Any]]
    safe_to_retry: bool
    group: str

    def prepare(
        self,
        *,
        params: dict[str, Any] | None = None,
        path_params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[str, bytes]:
        params, path_params = params or {}, path_params or {}
        known_query = {p["name"] for p in self.parameters if p["in"] == "query"}
        known_path = {p["name"] for p in self.parameters if p["in"] == "path"}
        if params.keys() - known_query or path_params.keys() - known_path:
            raise RequestValidationError("Unknown HTTP parameter")
        path = self.path
        query: list[tuple[str, str]] = []
        for p in self.parameters:
            source = path_params if p["in"] == "path" else params
            value = source.get(p["name"])
            if value is None:
                if p.get("required"):
                    raise RequestValidationError(f"{p['name']} is required")
                continue
            parsed = parameter_value(value, p["schema"], p["name"])
            if p["in"] == "path":
                if not parsed:
                    raise RequestValidationError(f"{p['name']} cannot be empty")
                if parsed in {".", ".."}:
                    raise RequestValidationError("Path parameters cannot be dot segments")
                path = path.replace("{" + p["name"] + "}", quote(parsed, safe=""))
            elif isinstance(parsed, list):
                query.extend((p["name"], v) for v in parsed)
            else:
                query.append((p["name"], parsed))
        if self.body is not None:
            if body is None:
                raise RequestValidationError("JSON request body is required")
            try:
                self.body.model_validate(body)
                content = encode_json(body)
            except ValidationError, ValueError, TypeError:
                raise RequestValidationError(f"Invalid JSON body for {self.name}") from None
        else:
            if body is not None:
                raise RequestValidationError("This endpoint does not accept a JSON body")
            content = b""
        return path + ("?" + urlencode(query, quote_via=quote) if query else ""), content
