from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolReward:
    total: float
    components: dict[str, float]
    details: dict


def compute_tool_reward(
    tool_name: str,
    execution_result: dict,
    expected_output: str | None = None,
) -> ToolReward:
    success = execution_result.get("success", False)
    stdout = execution_result.get("stdout", "")
    stderr = execution_result.get("stderr", "")
    exit_code = execution_result.get("exit_code", -1)
    timed_out = execution_result.get("timed_out", False)

    components = {}
    details = {}

    if timed_out:
        components["timeout"] = -1.0
        details["reason"] = "execution timed out"
        return ToolReward(total=-1.0, components=components, details=details)

    if tool_name == "cargo_test":
        if success:
            stdout_lower = stdout.lower()
            test_count = stdout.count("test result:")
            if test_count > 0:
                details["test_runs"] = test_count
            # Key off the explicit summary line, not loose substrings like
            # "failed" (cargo always prints "0 failed" on green runs).
            if "test result: failed" in stdout_lower:
                components["test_pass"] = -0.5
                components["all_tests_pass"] = -0.3
            else:
                components["test_pass"] = 1.0
                if "test result: ok" in stdout_lower:
                    components["all_tests_pass"] = 0.5
        else:
            components["test_pass"] = -1.0
            details["error_snippet"] = stderr[:500] if stderr else "unknown error"

    elif tool_name == "read_file":
        # Info-gathering step. Small positive shaping for successful reads,
        # negative for missing files (helps the model preserve correct paths).
        if success:
            components["read_success"] = 0.2
        else:
            components["read_success"] = -0.3
            details["error_snippet"] = stderr[:200] if stderr else "unknown"

    elif tool_name == "apply_patch":
        if success:
            components["patch_applied"] = 0.5
        else:
            components["patch_applied"] = -0.5
            details["error_snippet"] = stderr[:200] if stderr else "unknown"

    elif tool_name == "cargo_run":
        if success:
            components["run_success"] = 1.0
            details["exit_code"] = exit_code
            if expected_output is not None:
                if stdout.strip() == expected_output.strip():
                    components["output_match"] = 1.0
                else:
                    components["output_match"] = -0.5
                    details["expected"] = expected_output[:200]
                    details["actual"] = stdout[:200]
        else:
            components["run_success"] = -1.0
            details["error_snippet"] = stderr[:500] if stderr else "unknown error"

    else:
        components["unknown_tool"] = -0.5

    total = sum(components.values())
    return ToolReward(total=total, components=components, details=details)
