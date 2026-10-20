import re
from copy import deepcopy
from typing import Annotated, Any, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StrictStr,
    model_validator,
)

from ..metadata import ResponseMetadata


def int64_string(value: str) -> str:
    if not re.fullmatch(r"-?\d+", value) or not -(2**63) <= int(value) < 2**63:
        raise ValueError("Expected a signed int64 string")
    return value


def uint64_string(value: str) -> str:
    if not re.fullmatch(r"\d+", value) or not 0 <= int(value) < 2**64:
        raise ValueError("Expected an unsigned int64 string")
    return value


Int64String = Annotated[StrictStr, AfterValidator(int64_string)]
UInt64String = Annotated[StrictStr, AfterValidator(uint64_string)]


class OpenValue(RootModel[Any]):
    """An empty schema permits arbitrary JSON, not just objects."""

    def to_api_dict(self) -> Any:
        return deepcopy(self.root)


class WireModel(BaseModel):
    """Typed wire contract. Missing values are tracked by model_fields_set."""

    model_config = ConfigDict(
        extra="allow", populate_by_name=True, hide_input_in_errors=True, allow_inf_nan=False
    )
    _nullable_fields: ClassVar[frozenset[str]] = frozenset()
    metadata: ResponseMetadata | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="before")
    @classmethod
    def reject_nonnullable_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for name, info in cls.model_fields.items():
                alias = info.alias or name
                if name not in cls._nullable_fields:
                    if (alias in data and data[alias] is None) or (
                        name in data and data[name] is None
                    ):
                        raise ValueError(f"{alias} does not accept null")
        return data

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_unset=True, mode="python")
