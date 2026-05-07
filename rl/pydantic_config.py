from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ConfigDict


class BaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


T = TypeVar("T")


def cli(_: type[T]) -> T:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "@":
        data = tomllib.loads(Path(args[1]).read_text())
        return _.model_validate(data)
    raise RuntimeError(f"Unsupported CLI args: {args}")
