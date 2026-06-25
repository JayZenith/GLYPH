#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.rust.executor import RustExecutor
from agent_runtime.rust.results import format_result_block
from agent_runtime.rust.runtime import execute_rust_tool, rewrite_params_for_sandbox
from synthetic_data.validate_dataset import family_sequence_is_valid, normalize_family

SYSTEM_PROMPT = "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."
RUN_FAMILIES = {"patch_run_pass", "patch_run_recover", "run_only"}
TEST_FAMILIES = {"patch_test_pass", "patch_test_recover", "test_only"}
PATCH_FAMILIES = {
    "patch_test_pass",
    "patch_run_pass",
    "patch_test_recover",
    "patch_run_recover",
}


def _extract_output_text(batch_obj: dict) -> str:
    body = batch_obj.get("response", {}).get("body", batch_obj)
    if isinstance(body, dict) and isinstance(body.get("output_text"), str):
        return body["output_text"]
    if isinstance(body, dict):
        parts: list[str] = []
        for item in body.get("output", []) or []:
            for content in item.get("content", []) or []:
                text = content.get("text") or content.get("value")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    if isinstance(batch_obj.get("spec"), dict):
        return json.dumps(batch_obj["spec"])
    return json.dumps(batch_obj)


def _load_specs(path: Path) -> tuple[list[tuple[str, dict]], list[dict]]:
    specs: list[tuple[str, dict]] = []
    rejects: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        obj = json.loads(raw)
        custom_id = obj.get("custom_id", f"line-{line_no}")
        text = _extract_output_text(obj).strip()
        try:
            spec = json.loads(text)
        except json.JSONDecodeError as exc:
            rejects.append({
                "custom_id": custom_id,
                "errors": [f"invalid JSON spec: {exc}"],
                "text_preview": text[:1000],
            })
            continue
        specs.append((custom_id, spec))
    return specs, rejects


def _safe_case_id(value: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return value or "case"


def _write_files(project: Path, files: dict[str, str]) -> None:
    if "Cargo.toml" not in files:
        raise ValueError("missing Cargo.toml")
    for rel, content in files.items():
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise ValueError(f"unsafe file path {rel!r}")
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _has_nonempty_section(cargo_toml: str, section_names: set[str]) -> bool:
    active = False
    for raw in cargo_toml.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        section = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]", line)
        if section:
            active = section.group(1) in section_names
            continue
        if active:
            return True
    return False


def _call_line(tool: str, call_id: str, params: dict) -> str:
    payload = {"id": call_id, **params}
    args = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if tool == "read_file":
        return f"CALL read_file {args}"
    if tool == "apply_patch":
        return f"CALL apply_patch {args}"
    if tool == "cargo_test":
        return f"CALL cargo_test {args}"
    if tool == "cargo_run":
        return f"CALL cargo_run {args}"
    raise ValueError(f"unknown tool {tool}")


def _trace_path(case_id: str, rel: str) -> str:
    return f"runs/rlvr1/rust_cases/{case_id}/{rel}"


def _step_params_for_trace(case_id: str, step: dict) -> dict:
    tool = step["tool"]
    if tool in {"read_file", "apply_patch"}:
        params = {"file_path": _trace_path(case_id, step["file_path"])}
        if tool == "apply_patch":
            params["find"] = step["find"]
            params["replace"] = step["replace"]
        return params
    if tool in {"cargo_test", "cargo_run"}:
        return {"project_path": f"runs/rlvr1/rust_cases/{case_id}"}
    raise ValueError(f"unknown tool {tool}")


def _render_trace(spec: dict, case_id: str, calls: list[tuple[str, dict, str]], final: str) -> str:
    user = spec["user"].format(project_root=f"runs/rlvr1/rust_cases/{case_id}")
    parts = [
        f"<|im_start|>system\n{SYSTEM_PROMPT}\n<|im_end|>",
        f"<|im_start|>user\n{user}\n<|im_end|>",
    ]
    for idx, (tool, params, result_block) in enumerate(calls, 1):
        cid = f"c{idx}"
        parts.append(f"<|im_start|>assistant\n{_call_line(tool, cid, params)}\n<|im_end|>")
        parts.append(f"<|im_start|>tool\n{result_block}\n<|im_end|>")
    if not final.startswith("FINAL: "):
        final = "FINAL: " + final.removeprefix("FINAL:").strip()
    parts.append(f"<|im_start|>assistant\n{final}\n<|im_end|>")
    return "\n\n".join(parts)


def _validate_spec(spec: dict) -> list[str]:
    errors: list[str] = []
    for key in ("family", "case_id", "difficulty", "user", "expected_tool_sequence", "expected_output", "files", "steps", "final"):
        if key not in spec:
            errors.append(f"missing {key}")
    if errors:
        return errors
    family = normalize_family(spec["family"])
    if family is None:
        errors.append("missing family")
        return errors
    spec["family"] = family
    if family not in RUN_FAMILIES | TEST_FAMILIES:
        errors.append(f"unknown family {family!r}")
        return errors
    tools = [step.get("tool") for step in spec["steps"]]
    if spec["expected_tool_sequence"] != tools:
        errors.append("expected_tool_sequence mismatch")
    if not family_sequence_is_valid(family, tools):
        errors.append(f"steps tools {tools} invalid for family {family}")
    if "{project_root}" not in spec["user"]:
        errors.append("user missing {project_root}")
    if family in {"patch_run_pass", "patch_run_recover", "run_only"}:
        if not isinstance(spec["expected_output"], str):
            errors.append("cargo_run family needs string expected_output")
    elif spec["expected_output"] is not None:
        errors.append("non-cargo_run family expected_output must be null")
    errors.extend(_validate_files_and_steps(spec))
    return errors


def _result_preview(result) -> dict:
    return {
        "success": result.success,
        "stdout": result.stdout[:1000],
        "stderr": result.stderr[:1000],
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
    }


def _expected_statuses(family: str) -> list[str]:
    if family in {"patch_test_pass", "patch_run_pass", "test_only", "run_only"}:
        return ["success"]
    return []


def _validate_files_and_steps(spec: dict) -> list[str]:
    errors: list[str] = []
    family = spec["family"]
    files = spec["files"]
    steps = spec["steps"]
    if not isinstance(files, dict):
        return ["files must be an object"]
    allowed = {"Cargo.toml", "src/lib.rs", "src/main.rs"}
    unknown = sorted(set(files) - allowed)
    if unknown:
        errors.append(f"unknown file paths: {unknown}")
    if not isinstance(files.get("Cargo.toml"), str):
        errors.append("Cargo.toml must be a string")
        return errors
    cargo_toml = files["Cargo.toml"]
    if not re.search(r"""edition\s*=\s*["']2021["']""", cargo_toml):
        errors.append("Cargo.toml must set edition 2021")
    if _has_nonempty_section(cargo_toml, {"dependencies", "dev-dependencies", "build-dependencies"}):
        errors.append("Cargo.toml must not declare dependencies")

    if family in RUN_FAMILIES:
        if set(files) != {"Cargo.toml", "src/main.rs"}:
            errors.append("cargo_run families must contain exactly Cargo.toml and src/main.rs")
    elif family in TEST_FAMILIES:
        if set(files) != {"Cargo.toml", "src/lib.rs"}:
            errors.append("cargo_test families must contain exactly Cargo.toml and src/lib.rs")
    if family in TEST_FAMILIES and "#[test]" not in files.get("src/lib.rs", ""):
        errors.append("cargo_test families must include at least one #[test]")

    if not isinstance(steps, list):
        return errors + ["steps must be an array"]

    file_state = {path: content for path, content in files.items() if isinstance(content, str)}
    patched_files: list[str] = []
    verifier_statuses: list[str] = []
    for idx, step in enumerate(steps, 1):
        tool = step.get("tool")
        if tool in {"read_file", "apply_patch"}:
            file_path = step.get("file_path")
            if file_path not in {"src/lib.rs", "src/main.rs"}:
                errors.append(f"step {idx}: invalid file_path {file_path!r}")
            elif file_path not in file_state:
                errors.append(f"step {idx}: file_path {file_path!r} not present")
            if tool == "read_file" and "expect_status" in step:
                errors.append(f"step {idx}: read_file must not include expect_status")
            if tool == "apply_patch":
                find = step.get("find")
                replace = step.get("replace")
                if not isinstance(find, str) or not isinstance(replace, str):
                    errors.append(f"step {idx}: apply_patch needs string find/replace")
                elif isinstance(file_path, str) and file_path in file_state:
                    count = file_state[file_path].count(find)
                    if count != 1:
                        errors.append(f"step {idx}: find occurs {count} times, expected once")
                    else:
                        file_state[file_path] = file_state[file_path].replace(find, replace, 1)
                        patched_files.append(file_path)
                if "expect_status" in step:
                    errors.append(f"step {idx}: apply_patch must not include expect_status")
        elif tool in {"cargo_test", "cargo_run"}:
            status = step.get("expect_status")
            if status not in {"failed", "success"}:
                errors.append(f"step {idx}: {tool} needs expect_status failed|success")
            else:
                verifier_statuses.append(status)
        else:
            errors.append(f"step {idx}: unknown tool {tool!r}")

    if family in PATCH_FAMILIES:
        read_file = steps[0].get("file_path") if steps and steps[0].get("tool") == "read_file" else None
        first_patch = next((step.get("file_path") for step in steps if step.get("tool") == "apply_patch"), None)
        if read_file != first_patch:
            errors.append("first read_file must read the file being patched")
    if family in {"patch_test_recover", "patch_run_recover"}:
        if len(verifier_statuses) < 2 or verifier_statuses[-1] != "success" or any(status != "failed" for status in verifier_statuses[:-1]):
            errors.append(f"verifier statuses {verifier_statuses} must be one or more failed then success")
    elif verifier_statuses != _expected_statuses(family):
        errors.append(f"verifier statuses {verifier_statuses} != expected {_expected_statuses(family)}")
    return errors


def materialize_one(custom_id: str, spec: dict, source_root: Path, cases_root: Path, timeout: int) -> tuple[dict | None, list[str]]:
    errors = _validate_spec(spec)
    if errors:
        return None, [f"{custom_id}: {e}" for e in errors]

    case_id = _safe_case_id(f"{custom_id}_{spec['case_id']}")
    source_project = source_root / case_id
    run_project = cases_root / case_id
    if source_project.exists():
        shutil.rmtree(source_project)
    if run_project.exists():
        shutil.rmtree(run_project)
    _write_files(source_project, spec["files"])
    shutil.copytree(source_project, run_project)

    executor = RustExecutor(timeout=timeout)
    calls: list[tuple[str, dict, str]] = []
    last_result = None
    for idx, step in enumerate(spec["steps"], 1):
        tool = step["tool"]
        trace_params = _step_params_for_trace(case_id, step)
        exec_params = rewrite_params_for_sandbox(trace_params, f"runs/rlvr1/rust_cases/{case_id}", str(run_project))
        result = execute_rust_tool(
            executor,
            tool,
            exec_params,
            expected_output=spec["expected_output"] if tool == "cargo_run" else None,
        )
        expected_status = step.get("expect_status")
        actual_status = "success" if result.success else "failed"
        if expected_status and actual_status != expected_status:
            return None, [{
                "message": f"{custom_id}: step {idx} {tool} status {actual_status} != {expected_status}",
                "step_index": idx,
                "tool": tool,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "result": _result_preview(result),
            }]
        calls.append((tool, trace_params, format_result_block(f"c{idx}", result)))
        last_result = result

    if last_result is None or not last_result.success:
        return None, [{
            "message": f"{custom_id}: final tool did not succeed",
            "result": _result_preview(last_result),
        }]

    trace = _render_trace(spec, case_id, calls, spec["final"])
    row = {
        "trace": trace,
        "family": spec["family"],
        "case_id": case_id,
        "difficulty": spec["difficulty"],
        "expected_tool_sequence": spec["expected_tool_sequence"],
        "expected_output": spec["expected_output"],
    }
    return row, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs", type=Path)
    parser.add_argument("--source-root", type=Path, default=Path("runs/rlvr1/rust_cases"))
    parser.add_argument("--cases-root", type=Path, default=Path("runs/materialize_specs_cases"))
    parser.add_argument("--families-dir", type=Path, default=Path("synthetic_data/families"))
    parser.add_argument("--rejects", type=Path, default=Path("synthetic_data/batch_pilot_100/rejects.jsonl"))
    parser.add_argument("--tool-timeout", type=int, default=30)
    args = parser.parse_args()

    args.families_dir.mkdir(parents=True, exist_ok=True)
    if args.cases_root.exists():
        shutil.rmtree(args.cases_root)
    args.cases_root.mkdir(parents=True, exist_ok=True)

    specs, rejects = _load_specs(args.specs)
    accepted: dict[str, list[dict]] = defaultdict(list)
    for custom_id, spec in specs:
        row, errors = materialize_one(custom_id, spec, args.source_root, args.cases_root, args.tool_timeout)
        if row:
            accepted[row["family"]].append(row)
        else:
            rejects.append({"custom_id": custom_id, "errors": errors, "spec": spec})

    for family, rows in accepted.items():
        path = args.families_dir / f"{family}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    args.rejects.parent.mkdir(parents=True, exist_ok=True)
    with args.rejects.open("w", encoding="utf-8") as handle:
        for row in rejects:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps({"accepted": {k: len(v) for k, v in sorted(accepted.items())}, "rejected": len(rejects)}, indent=2))
    return 0 if not rejects else 1


if __name__ == "__main__":
    raise SystemExit(main())
