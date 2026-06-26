#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import statistics
import sys
import tempfile
import types
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from agent_runtime.chatml import (
    assert_glyph_template_parity,
    render_messages,
    render_prompt,
    render_tool_turn,
)
from agent_runtime.protocol import call_syntax_errors, ended_cleanly_after_final, parse_calls
from agent_runtime.rust.executor import ExecutionResult


ROLLOUT_PATHS = [
    Path("results/RLVR1/rollouts4/step_0/train_rollouts.jsonl"),
    Path("results/RLVR1/rollouts4/step_95/train_rollouts.jsonl"),
]
VERIFIERS = {"cargo_test", "cargo_run"}


def _install_verifiers_stub() -> None:
    if "verifiers" in sys.modules:
        return
    vf = types.ModuleType("verifiers")
    vf.MultiTurnEnv = type("MultiTurnEnv", (), {"__init__": lambda self, *a, **k: None})
    vf.Rubric = type(
        "Rubric",
        (),
        {"__init__": lambda self, *a, **k: None, "add_reward_func": lambda self, *a, **k: None},
    )
    sys.modules["verifiers"] = vf


_install_verifiers_stub()
from rl.reward import (  # noqa: E402
    DEFAULT_REWARD_CONFIG,
    _rust_tool_reward,
)
from rl.task_format import load_prompts  # noqa: E402


def result_block(call_id: str, success: bool) -> str:
    status = "success" if success else "failed"
    stderr = "" if success else "\nstderr:\nfailed"
    return f"RESULT {call_id}:\nstatus: {status}\nstdout:\nok{stderr}"


def execution_result(success: bool) -> ExecutionResult:
    return ExecutionResult(
        success=success,
        stdout="ok",
        stderr="" if success else "failed",
        exit_code=0 if success else 1,
    )


def executed_results_from_blocks(results: list[str]) -> dict[str, ExecutionResult]:
    executed: dict[str, ExecutionResult] = {}
    for block in results:
        first = block.splitlines()[0]
        if first.startswith("RESULT ") and first.endswith(":"):
            call_id = first.removeprefix("RESULT ").removesuffix(":")
            executed[call_id] = execution_result("status: success" in block)
    return executed


def call(tool: str, call_id: str, **params: str) -> str:
    payload = json.dumps({"id": call_id, **params}, separators=(",", ":"))
    return f"CALL {tool} {payload}"


def raw_trace(assistant: str, results: list[str]) -> str:
    by_id = {}
    for block in results:
        first = block.splitlines()[0]
        if first.startswith("RESULT ") and first.endswith(":"):
            by_id[first.removeprefix("RESULT ").removesuffix(":")] = block

    parts = []
    for line in assistant.splitlines():
        parts.append(line)
        parsed = parse_calls(line)
        if parsed and parsed[0].id in by_id:
            parts.append(by_id[parsed[0].id])
    return "\n".join(parts)


def trajectory_from_assistant_lines(assistant: str, results: list[str]) -> list[dict]:
    by_id = {}
    for block in results:
        first = block.splitlines()[0]
        if first.startswith("RESULT ") and first.endswith(":"):
            by_id[first.removeprefix("RESULT ").removesuffix(":")] = block

    trajectory = []
    for line in assistant.splitlines():
        completion = [{"role": "assistant", "content": line}]
        parsed = parse_calls(line)
        if parsed and parsed[0].id in by_id:
            completion.append({"role": "tool", "content": by_id[parsed[0].id]})
        trajectory.append({"completion": completion})
    return trajectory


def score(assistant: str, results: list[str], expected_tool: str = "read_file") -> float:
    calls = parse_calls(assistant)
    return asyncio.run(
        _rust_tool_reward(
            [{"role": "assistant", "content": assistant}],
            state={
                "executed_tool_calls": calls,
                "executed_results": executed_results_from_blocks(results),
                "executed_result_blocks": results,
                "raw_chatml_transcript": raw_trace(assistant, results),
                "trajectory": trajectory_from_assistant_lines(assistant, results),
            },
            info={
                "expected_tool": expected_tool,
            },
        )
    )


def score_with_raw_trace(assistant: str, results: list[str], raw: str) -> float:
    calls = parse_calls(assistant)
    return asyncio.run(
        _rust_tool_reward(
            [{"role": "assistant", "content": assistant}],
            state={
                "executed_tool_calls": calls,
                "executed_results": executed_results_from_blocks(results),
                "executed_result_blocks": results,
                "raw_chatml_transcript": raw,
                "trajectory": trajectory_from_assistant_lines(assistant, results),
            },
            info={
                "expected_tool": "read_file",
            },
        )
    )


def score_with_state(assistant: str, results: list[str], state: dict) -> float:
    return asyncio.run(
        _rust_tool_reward(
            [{"role": "assistant", "content": assistant}],
            state=state,
            info={
                "expected_tool": "read_file",
            },
        )
    )


class RewardGoldenTests(unittest.TestCase):
    """Reliability-lift reward. Only exact heldout-style success is positive;
    invalid cargo success is allowed to be less bad than failed cargo, but it
    cannot become a positive optimization target.
    """

    READ = call("read_file", "c1", file_path="src/lib.rs")
    PATCH = call("apply_patch", "c2", file_path="src/lib.rs", find="bug", replace="fix")
    OK = call("cargo_test", "c3", project_path=".")
    FAIL = call("cargo_test", "c3", project_path=".")
    SOLVED = [result_block("c1", True), result_block("c2", True), result_block("c3", True)]
    UNSOLVED = [result_block("c1", True), result_block("c2", True), result_block("c3", False)]

    def _solve_stop(self):
        return score("\n".join([self.READ, self.PATCH, self.OK, "FINAL: done"]), self.SOLVED)

    def _solve_nostop(self):
        return score("\n".join([self.READ, self.PATCH, self.OK]), self.SOLVED)

    def _solve_stop_with_generated_chatml_end(self):
        return score("\n".join([self.READ, self.PATCH, self.OK, "FINAL: done<|im_end|>"]), self.SOLVED)

    def _graceful(self):
        return score("\n".join([self.READ, self.PATCH, self.FAIL, "FINAL: tried"]), self.UNSOLVED)

    def _loop(self):
        return score("\n".join([self.READ, self.PATCH, self.FAIL]), self.UNSOLVED)

    def test_json_call_parser(self) -> None:
        parsed = parse_calls('CALL read_file {"id":"c1","file_path":"src/lib.rs"}')
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].tool, "read_file")
        self.assertEqual(parsed[0].id, "c1")
        self.assertEqual(parsed[0].params, {"file_path": "src/lib.rs"})

    def test_legacy_parenthesized_call_is_invalid(self) -> None:
        legacy = 'CALL read_file(id="c1", file_path="src/lib.rs")'
        self.assertEqual(parse_calls(legacy), [])
        self.assertTrue(call_syntax_errors(legacy))

    def test_missing_call_id_is_invalid(self) -> None:
        missing = 'CALL read_file {"file_path":"src/lib.rs"}'
        self.assertEqual(parse_calls(missing), [])
        self.assertTrue(any("Missing CALL id" in err for err in call_syntax_errors(missing)))

    def test_solving_dominates(self) -> None:
        # Solving beats every non-solving outcome even with finalization shaping.
        self.assertGreater(self._solve_stop(), self._graceful())
        self.assertGreater(self._solve_stop(), self._loop())

    def test_clean_final_is_preferred(self) -> None:
        self.assertGreater(self._solve_stop(), self._solve_nostop())
        self.assertEqual(self._solve_stop_with_generated_chatml_end(), self._solve_stop())
        self.assertGreater(self._graceful(), self._loop())

    def test_churn_after_success_is_penalized(self) -> None:
        read_again = call("read_file", "c4", file_path="src/lib.rs")
        more = score(
            "\n".join([self.READ, self.PATCH, self.OK, read_again, "FINAL: done"]),
            self.SOLVED + [result_block("c4", True)],
        )
        self.assertLess(more, self._solve_stop())
        self.assertLess(more, self._solve_nostop())

    def test_cargo_success_without_clean_final_is_not_positive(self) -> None:
        # Heldout counts cargo success without clean FINAL as invalid. It may
        # be less bad than a failed verifier trace, but it must not be a
        # positive optimization target.
        self.assertEqual(DEFAULT_REWARD_CONFIG["verifier_success_bonus"], 0.0)
        self.assertGreater(self._solve_nostop(), self._loop())
        self.assertLessEqual(self._solve_nostop(), 0.0)
        self.assertGreater(self._solve_stop(), 8.0)

    def test_dirty_final_after_cargo_success_is_not_positive(self) -> None:
        dirty = score(
            "\n".join([self.READ, self.PATCH, self.OK, "FINAL: done", "extra tokens"]),
            self.SOLVED,
        )
        self.assertLessEqual(dirty, 0.0)

    def test_leading_prose_before_final_does_not_get_clean_solve_reward(self) -> None:
        assistant = "\n".join([self.READ, self.PATCH, self.OK, "Fixed it.\nFINAL: done"])
        calls = parse_calls(assistant)
        dirty = score_with_state(
            assistant,
            self.SOLVED,
            {
                "executed_tool_calls": calls,
                "executed_results": executed_results_from_blocks(self.SOLVED),
                "executed_result_blocks": self.SOLVED,
                "raw_chatml_transcript": raw_trace(assistant, self.SOLVED),
                "trajectory": [
                    {"completion": [{"role": "assistant", "content": self.READ}, {"role": "tool", "content": self.SOLVED[0]}]},
                    {"completion": [{"role": "assistant", "content": self.PATCH}, {"role": "tool", "content": self.SOLVED[1]}]},
                    {"completion": [{"role": "assistant", "content": self.OK}, {"role": "tool", "content": self.SOLVED[2]}]},
                    {"completion": [{"role": "assistant", "content": "Fixed it.\nFINAL: done"}]},
                ],
            },
        )
        self.assertLessEqual(dirty, 0.0)

    def test_unexecuted_trailing_call_after_success_blocks_clean_solve_reward(self) -> None:
        trailing = call("read_file", "c4", file_path="src/lib.rs")
        assistant = "\n".join([self.READ, self.PATCH, self.OK, trailing, "FINAL: done"])
        executed_calls = parse_calls("\n".join([self.READ, self.PATCH, self.OK]))
        state = {
            "executed_tool_calls": executed_calls,
            "executed_results": executed_results_from_blocks(self.SOLVED),
            "executed_result_blocks": self.SOLVED,
            "raw_chatml_transcript": raw_trace(assistant, self.SOLVED),
            "trajectory": trajectory_from_assistant_lines(assistant, self.SOLVED),
        }
        reward = score_with_state(assistant, self.SOLVED, state)
        self.assertLessEqual(reward, 0.0)

    def test_format_floor_still_applies(self) -> None:
        # Emitting no tool call at all is still discouraged (format floor).
        no_call = score("FINAL: done", [])
        self.assertLess(no_call, self._loop())

    def test_unverified_rollout_is_penalized(self) -> None:
        unverified = score("\n".join([self.READ, self.PATCH, "FINAL: done"]), self.SOLVED[:2])
        self.assertLess(unverified, 0.0)

    def test_reward_uses_resolved_info_fallback(self) -> None:
        assistant = "\n".join([self.READ, self.PATCH, self.OK, "FINAL: done"])
        reward = asyncio.run(
            _rust_tool_reward(
                [{"role": "assistant", "content": assistant}],
                state={
                    "resolved_info": {"expected_tool": "read_file"},
                    "executed_tool_calls": parse_calls(assistant),
                    "executed_results": executed_results_from_blocks(self.SOLVED),
                    "executed_result_blocks": self.SOLVED,
                    "raw_chatml_transcript": raw_trace(assistant, self.SOLVED),
                    "trajectory": trajectory_from_assistant_lines(assistant, self.SOLVED),
                },
            )
        )
        self.assertEqual(reward, self._solve_stop())

    def test_worst_case_is_bounded(self) -> None:
        self.assertGreater(self._loop(), -8.0)
        self.assertGreater(score("FINAL: done", []), -8.0)

    def test_failed_verifier_retries_are_bounded(self) -> None:
        fail1 = call("cargo_test", "c3", project_path=".")
        fail2 = call("cargo_test", "c4", project_path=".")
        ok = call("cargo_test", "c5", project_path=".")
        one_fail_then_pass = score(
            "\n".join([self.READ, self.PATCH, fail1, fail2, ok, "FINAL: done"]),
            [
                result_block("c1", True),
                result_block("c2", True),
                result_block("c3", False),
                result_block("c4", False),
                result_block("c5", True),
            ],
        )
        self.assertLess(one_fail_then_pass, self._solve_stop())
        self.assertGreater(one_fail_then_pass, 6.0)

    def test_malformed_call_syntax_cannot_parse_or_score_well(self) -> None:
        malformed = 'CALL read_file {"id":"c1","file_path":"src/lib.rs",}'
        self.assertEqual(parse_calls(malformed), [])
        self.assertTrue(call_syntax_errors(malformed))
        self.assertLess(score(malformed + "\nFINAL: done", []), self._loop())

    def test_malformed_call_with_chatml_end_cannot_score_well(self) -> None:
        malformed = 'CALL read_file {"id":"c1","file_path":"src/lib.rs",}<|im_end|>'
        self.assertLess(score(malformed, []), self._loop())

    def test_malformed_calls_across_message_turns_are_invalid_with_generated_boundaries(self) -> None:
        completion = [
            {"role": "assistant", "content": self.READ + ")<|im_end|>"},
            {"role": "assistant", "content": self.PATCH + "<|im_end|>"},
            {"role": "assistant", "content": self.OK + "<|im_end|>"},
            {"role": "assistant", "content": "FINAL: done"},
        ]
        calls = parse_calls("\n".join(m["content"] for m in completion))
        reward = asyncio.run(
            _rust_tool_reward(
                completion,
                state={
                    "executed_tool_calls": calls,
                    "executed_results": executed_results_from_blocks(self.SOLVED),
                    "executed_result_blocks": self.SOLVED,
                    "raw_chatml_transcript": raw_trace(
                        "\n".join(m["content"] for m in completion),
                        self.SOLVED,
                    ),
                },
                info={
                    "expected_tool": "read_file",
                },
            )
        )
        self.assertLessEqual(reward, 0.0)

    def test_terminal_chatml_end_after_final_is_allowed(self) -> None:
        clean = "\n".join([self.READ, self.PATCH, self.OK, "FINAL: done<|im_end|>"])
        self.assertEqual(score(clean, self.SOLVED), self._solve_stop())

    def test_bad_cargo_project_path_blocks_top_reward(self) -> None:
        bad_cargo = call("cargo_test", "c3", project_path="/tmp/case/src/main.rs")
        reward = score(
            "\n".join([self.READ, self.PATCH, bad_cargo, "FINAL: done"]),
            self.SOLVED,
        )
        self.assertLess(reward, self._solve_nostop())

    def test_multiline_final_does_not_get_clean_solve_reward(self) -> None:
        dirty_final = score(
            "\n".join([self.READ, self.PATCH, self.OK, "FINAL: done", ".waitKey" * 9]),
            self.SOLVED,
        )
        self.assertLess(dirty_final, self._solve_stop())
        self.assertLessEqual(dirty_final, 0.0)

    def test_generated_token_final_tail_is_not_clean(self) -> None:
        dirty_final = score(
            "\n".join([self.READ, self.PATCH, self.OK, "FINAL: done<|endoftext|>"]),
            self.SOLVED,
        )
        self.assertLess(dirty_final, self._solve_stop())
        self.assertLessEqual(dirty_final, 0.0)


def assistant_text(row: dict) -> str:
    return "\n".join(
        str(m.get("content") or "")
        for m in row.get("completion", [])
        if isinstance(m, dict) and m.get("role") == "assistant"
    )


def tool_text(row: dict) -> str:
    return "\n".join(
        str(m.get("content") or "")
        for m in row.get("completion", [])
        if isinstance(m, dict) and m.get("role") == "tool"
    )


def _result_for(call_id: str, text: str) -> dict | None:
    match = re.search(
        r"RESULT\s+" + re.escape(call_id) + r":\n(.*?)(?=\nRESULT\s+[A-Za-z0-9_\-]+:|\Z)",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    return {"success": "status: success" in body}


def trajectory(row: dict) -> tuple[list[str], str, bool, bool, bool]:
    atext = assistant_text(row)
    ttext = tool_text(row)
    calls = parse_calls(atext)
    tools = [c.tool for c in calls]
    outcomes = [
        bool(result.get("success", False))
        for c in calls
        if c.tool in VERIFIERS
        for result in [_result_for(c.id, ttext)]
        if result is not None
    ]
    has_verifier = bool(outcomes) or any(t in VERIFIERS for t in tools)
    has_patch = "apply_patch" in tools
    has_final = "FINAL:" in atext
    clean_final = ended_cleanly_after_final(atext)
    executed = {c.tool for c in calls if _result_for(c.id, ttext) is not None}
    if outcomes and outcomes[-1] and clean_final:
        stage = "clean_final"
    elif outcomes and outcomes[-1]:
        stage = "terminal_pass"
    elif outcomes:
        stage = "failed_terminal"
    elif "apply_patch" in executed:
        stage = "patch"
    elif "read_file" in executed:
        stage = "read"
    else:
        stage = "quit"
    return tools, stage, has_patch, has_verifier, has_final


def reward_bucket(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if value < -4:
        return "<-4"
    if value < -2:
        return "[-4,-2)"
    if value < 0:
        return "[-2,0)"
    if value == 0:
        return "0"
    if value < 2:
        return "(0,2)"
    if value < 4:
        return "[2,4)"
    return ">=4"


def stream_rows(path: Path, limit: int):
    with path.open(encoding="utf-8") as handle:
        for idx, raw in enumerate(handle):
            if idx >= limit:
                break
            yield json.loads(raw)


def summarize_rollouts(paths: list[Path], sample: int) -> None:
    for path in paths:
        if not path.exists():
            print(f"\n{path}: missing")
            continue

        stage_counts: Counter[str] = Counter()
        reward_counts: Counter[str] = Counter()
        tool_counts: Counter[tuple[str, ...]] = Counter()
        pattern_counts: Counter[tuple[str, ...]] = Counter()
        examples: dict[tuple[str, ...], list[dict]] = defaultdict(list)
        rewards: list[float] = []
        patch = verifier = final = total = 0

        for row in stream_rows(path, sample):
            tools, stage, has_patch, has_verifier, has_final = trajectory(row)
            reward = float(row.get("reward", 0.0))
            pattern = tuple(tools) or ("<no_call>",)
            total += 1
            rewards.append(reward)
            stage_counts[stage] += 1
            reward_counts[reward_bucket(reward)] += 1
            tool_counts[tuple(tools)] += 1
            pattern_counts[pattern] += 1
            patch += has_patch
            verifier += has_verifier
            final += has_final
            if len(examples[pattern]) < 3:
                examples[pattern].append(
                    {"id": row.get("example_id"), "reward": round(reward, 3), "stage": stage}
                )

        print(f"\n{path} sample={total}")
        if not total:
            continue
        print(f"reward mean={statistics.mean(rewards):.3f} min={min(rewards):.3f} max={max(rewards):.3f}")
        print("stage distribution:", dict(stage_counts.most_common()))
        print("reward distribution:", dict(reward_counts.most_common()))
        print("tool sequence frequencies:", {str(k): v for k, v in tool_counts.most_common(10)})
        print(f"reaches apply_patch={patch / total:.1%} verifier={verifier / total:.1%} FINAL={final / total:.1%}")
        print("top trajectory patterns:")
        for pattern, count in pattern_counts.most_common(10):
            print(f"  {count:4d} {pattern} examples={examples[pattern]}")


class RlPromptFormatTests(unittest.TestCase):
    def test_chatml_prompt_loads_as_messages(self) -> None:
        row = {
            "prompt": (
                "<|im_start|>system\nsys\n<|im_end|>\n\n"
                "<|im_start|>user\nfix crate\n<|im_end|>\n\n"
                "<|im_start|>assistant\n"
            ),
            "expected_tool": "read_file",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
            prompts, stats = load_prompts(f.name)

        self.assertEqual(stats["skipped_malformed"], 0)
        self.assertEqual(
            prompts[0]["prompt"],
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "fix crate"},
            ],
        )

    def test_plain_prompt_loads_as_system_user_messages(self) -> None:
        row = {"prompt": "Fix the crate.", "expected_tool": "read_file"}
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
            prompts, _ = load_prompts(f.name)

        self.assertEqual([m["role"] for m in prompts[0]["prompt"]], ["system", "user"])
        self.assertEqual(prompts[0]["prompt"][1]["content"], "Fix the crate.")

    def test_internal_chatml_render_matches_sft_eval_protocol(self) -> None:
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "fix"},
            {"role": "assistant", "content": 'CALL read_file {"id":"c1"}<|im_end|>'},
            {"role": "tool", "content": "RESULT c1:\nstatus: success"},
            {"role": "assistant", "content": "FINAL: done"},
        ]
        rendered = render_messages(messages)
        self.assertIn("<|im_start|>tool\nRESULT c1:\nstatus: success\n<|im_end|>", rendered)
        self.assertNotIn("<tool_response>", rendered)
        self.assertNotIn("<|im_start|>user\n<|im_start|>system", rendered)

    def test_shared_chatml_renderer_matches_expected_bytes(self) -> None:
        self.assertEqual(
            render_prompt("fix crate", "sys"),
            (
                "<|im_start|>system\nsys\n<|im_end|>\n\n"
                "<|im_start|>user\nfix crate\n<|im_end|>\n\n"
                "<|im_start|>assistant\n"
            ),
        )
        self.assertEqual(
            render_tool_turn("RESULT c1:\nstatus: success"),
            (
                "\n\n<|im_start|>tool\nRESULT c1:\nstatus: success\n<|im_end|>\n\n"
                "<|im_start|>assistant\n"
            ),
        )
        assert_glyph_template_parity()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=200, help="Rows to stream per rollout file.")
    parser.add_argument("--no-rollouts", action="store_true")
    args = parser.parse_args()

    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(RewardGoldenTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(RlPromptFormatTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    if not args.no_rollouts:
        summarize_rollouts(ROLLOUT_PATHS, args.sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
