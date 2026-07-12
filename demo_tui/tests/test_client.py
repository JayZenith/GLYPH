from __future__ import annotations

import asyncio

from demo_tui.client import ScriptedCompletionClient


async def collect(client: ScriptedCompletionClient) -> str:
    return "".join([piece async for piece in client.stream("prompt")])


def test_scripted_completion_client_emits_eval_tool_sequence_and_resets() -> None:
    client = ScriptedCompletionClient(
        trace_prefix="runs/rlvr1/rust_cases/eval_case",
        chunk_size=7,
    )

    first = asyncio.run(collect(client))
    second = asyncio.run(collect(client))
    third = asyncio.run(collect(client))
    fourth = asyncio.run(collect(client))

    assert 'CALL read_file {"id":"c1"' in first
    assert "runs/rlvr1/rust_cases/eval_case/src/lib.rs" in first
    assert 'CALL apply_patch {"id":"c2"' in second
    assert "role != Role::Guest" in second
    assert 'CALL cargo_test {"id":"c3"' in third
    assert fourth.startswith("FINAL:")

    client.reset()
    assert 'CALL read_file {"id":"c1"' in asyncio.run(collect(client))
