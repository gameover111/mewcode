from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class LineResponse(Protocol):
    def iter_lines(self) -> Iterator[str]:
        ...


def iter_sse_data_lines(response: LineResponse) -> Iterator[str]:
    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            continue
        if not stripped.startswith("data:"):
            continue
        yield stripped.removeprefix("data:").strip()
