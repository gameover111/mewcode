from __future__ import annotations

from mewcode.providers.sse import iter_sse_data_lines


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self):
        yield from self._lines


def test_iter_sse_data_lines_filters_non_data_lines():
    response = FakeResponse(
        [
            "",
            ": ping",
            "event: message",
            'data: {"type":"delta"}',
            "data: [DONE]",
        ]
    )

    assert list(iter_sse_data_lines(response)) == ['{"type":"delta"}', "[DONE]"]


def test_iter_sse_data_lines_decodes_bytes():
    response = FakeResponse([b"data: hello"])

    assert list(iter_sse_data_lines(response)) == ["hello"]
