#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.validator import validate_trace


OUT = Path(__file__).parent / "gold_glyph_50.jsonl"


@dataclass(frozen=True)
class ToolParam:
    name: str
    kind: str
    description: str
    required: bool = True
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    params: tuple[ToolParam, ...]


def param(name: str, kind: str, description: str, required: bool = True) -> ToolParam:
    return ToolParam(name, kind, description, required)


def enum_param(name: str, values: tuple[str, ...], description: str, required: bool = True) -> ToolParam:
    return ToolParam(name, "enum", description, required, values)


def tool(name: str, description: str, *params: ToolParam) -> ToolDef:
    return ToolDef(name, description, params)


def render_tools(tools: list[ToolDef]) -> str:
    parts: list[str] = []
    for t in tools:
        lines = [
            "tool {",
            f"    name ↦ {t.name} •",
            f'    description ↦ "{t.description}" •',
            "    params ↦ {",
        ]
        row_parts = []
        for p in t.params:
            inner = [f'enum ↦ [ {" • ".join(p.enum_values)} ]' if p.enum_values else f"type ↦ {p.kind}"]
            if not p.required:
                inner.append("required ↦ false")
            inner.append(f'description ↦ "{p.description}"')
            row_parts.append(f"        {p.name} ↦ {{ {' • '.join(inner)} }}")
        lines.append(" •\n".join(row_parts) if row_parts else "")
        lines.append("    }")
        lines.append("}")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def seg(role: str, body: str) -> str:
    return f"<|im_start|>{role}\n{body}\n<|im_end|>"


def system_seg(text: str, tools: list[ToolDef] | None = None) -> str:
    body = [f"system「{text}」"]
    if tools:
        body.append(render_tools(tools))
    return seg("system", "\n".join(body))


def user_seg(text: str) -> str:
    return seg("user", f"user「{text}」🏷 usr1")


def plan_block(todos: list[str], rationale: str) -> str:
    lines = ["plan {", "    todo ↦ {"]
    for i, todo in enumerate(todos, start=1):
        sep = " •" if i < len(todos) else ""
        lines.append(f'        {i} ↦ "{todo}" ※ usr1{sep}')
    lines.extend(["    } •", f'    rationale ↦ "{rationale}"', "}"])
    return "\n".join(lines)


def think_act(thoughts: list[tuple[str, str, list[str]]]) -> str:
    lines = ["act {", "    think ↦ ["]
    for i, (text, tag, refs) in enumerate(thoughts):
        ref_text = f" ※ [ {' • '.join(refs)} ]" if refs else ""
        sep = " •" if i < len(thoughts) - 1 else ""
        lines.append(f'        「{text}」 𝑝 0.9 🏷 {tag}{ref_text}{sep}')
    lines.extend(["    ]", "}"])
    return "\n".join(lines)


def call_act(tool_name: str, args: list[tuple[str, str]], call_id: str, satisfies: int) -> str:
    lines = ["act {", "    call ↦ {"]
    rows = [f"        tool ↦ {tool_name}"]
    rows.extend(f'        {k} ↦ "{v}"' for k, v in args)
    rows.append(f"        id ↦ {call_id}")
    lines.append(" •\n".join(rows))
    lines.extend([f"    }} ⊨ {satisfies}", "}"])
    return "\n".join(lines)


def result_seg(data: str, tag: str) -> str:
    return seg("tool", f'result {{\n    data ↦ "{data}" 🏷 {tag}\n}}')


def response_block(text: str, refs: list[str], satisfies: int) -> str:
    return "\n".join([f"response「{text}」", f"※ [ {' • '.join(refs)} ]", f"⊨ {satisfies}"])


def assistant_seg(*blocks: str) -> str:
    return seg("assistant", "\n\n".join(blocks))


def join_trace(*segments: str) -> str:
    return "\n\n".join(segments)


def no_tool_trace(system: str, user: str, todo: str, rationale: str, think: str, response: str, note_tag: str) -> str:
    return join_trace(
        system_seg(system),
        user_seg(user),
        assistant_seg(
            plan_block([todo], rationale),
            think_act([(think, note_tag, ["usr1"])]),
            response_block(response, [note_tag], 1),
        ),
    )


def single_tool_trace(system: str, tools: list[ToolDef], user: str, todos: list[str], rationale: str,
                      call_tool: str, call_args: list[tuple[str, str]], call_id: str,
                      result_data: str, think: str, note_tag: str, response: str) -> str:
    return join_trace(
        system_seg(system, tools),
        user_seg(user),
        assistant_seg(plan_block(todos, rationale), call_act(call_tool, call_args, call_id, 1)),
        result_seg(result_data, call_id),
        assistant_seg(
            think_act([(think, note_tag, [call_id])]),
            response_block(response, [call_id, note_tag], 2),
        ),
    )


def multi_tool_trace(system: str, tools: list[ToolDef], user: str, todos: list[str], rationale: str,
                     call1_tool: str, call1_args: list[tuple[str, str]], call1_id: str, result1: str, think1: str, tag1: str,
                     call2_tool: str, call2_args: list[tuple[str, str]], call2_id: str, result2: str, think2: str, tag2: str,
                     response: str) -> str:
    return join_trace(
        system_seg(system, tools),
        user_seg(user),
        assistant_seg(plan_block(todos, rationale), call_act(call1_tool, call1_args, call1_id, 1)),
        result_seg(result1, call1_id),
        assistant_seg(think_act([(think1, tag1, [call1_id])]), call_act(call2_tool, call2_args, call2_id, 2)),
        result_seg(result2, call2_id),
        assistant_seg(think_act([(think2, tag2, [call1_id, call2_id])]), response_block(response, [call1_id, call2_id, tag2], 3)),
    )


def records() -> list[str]:
    rustdoc = [tool("rustdoc_lookup", "Returns concise documentation for a Rust symbol.", param("symbol", "string", "Rust symbol"))]
    cargo = [
        tool("cargo_check", "Runs cargo check on a Rust crate and returns the main compiler diagnostics.", param("crate_path", "string", "Path to the crate", required=False)),
        tool("cargo_test", "Runs cargo test and returns failing test output.", param("crate_path", "string", "Path to the crate", required=False), param("filter", "string", "Optional test filter", required=False)),
        tool("cargo_clippy", "Runs cargo clippy and returns the main lints.", param("crate_path", "string", "Path to the crate", required=False)),
        tool("rustdoc_lookup", "Returns concise documentation for a Rust type, trait, macro, or function.", param("symbol", "string", "Rust symbol to look up", required=False)),
    ]
    ci_tools = [
        tool("get_ci_logs", "Fetches CI logs for a run.", param("run_id", "string", "Run id")),
        tool("code_search", "Searches the codebase.", param("query", "string", "Search query")),
        tool("fetch_cached_incident", "Returns a cached incident note.", param("service", "string", "Service name")),
    ]
    sql_tools = [tool("run_sql", "Executes a read-only SQL query.", param("query", "string", "SQL query text"))]
    math_tools = [
        tool("solve_symbolic", "Performs symbolic math operations.", param("expression", "string", "Expression"), enum_param("operation", ("integrate", "differentiate", "simplify", "factor"), "Operation"), param("variable", "string", "Variable")),
        tool("derivative_check", "Differentiates a candidate and compares it to a target expression.", param("candidate_antiderivative", "string", "Candidate"), param("target_expression", "string", "Target"), param("variable", "string", "Variable")),
    ]
    file_tools = [tool("load_file", "Loads a file from disk and returns a short excerpt.", param("path", "string", "Path to load"))]
    git_tools = [
        tool("git_status", "Returns a concise git status (branch, dirty files, and staged changes).", param("repo_path", "string", "Path to the git repository", required=False)),
        tool("git_log", "Shows recent commits in a concise one-line format.", param("repo_path", "string", "Path to the git repository", required=False), param("limit", "number", "Maximum number of commits to show", required=False)),
    ]
    plan_tools = [
        tool("get_availability", "Returns weekly availability by teammate.", param("team_list", "string", "Comma-separated IDs", required=False), param("start_date", "string", "Start date", required=False), param("end_date", "string", "End date", required=False)),
        tool("create_project_plan", "Generates a short work breakdown.", param("project_name", "string", "Project name", required=False), param("objectives", "string", "Objectives", required=False), param("timeline_weeks", "string", "Timeline in weeks", required=False)),
    ]

    traces: list[str] = []

    traces.extend([
        no_tool_trace("You are a Rust language assistant who gives compact conceptual explanations.",
                      "In Rust, when would you choose an enum over a trait-object-based design? Give one concrete tradeoff and a simple rule of thumb.",
                      "Explain the tradeoff and give a short rule of thumb.",
                      "Define the main distinction, then give one practical heuristic.",
                      "Contrast closed sets of variants with open-ended extensibility, then end with one pragmatic selection rule.",
                      "Use an enum when you control a fixed set of variants and want exhaustive matching; use trait objects when you need open-ended implementations and can accept dynamic dispatch. Rule of thumb: fixed variants -> enum, plugin-like extensibility -> trait objects.",
                      "note_enum_vs_dyn"),
        no_tool_trace("You are a Rust async explainer who writes concise technical answers.",
                      "In async Rust, what does Send mean for a Future, and when do I need it?",
                      "Explain what Send on a Future guarantees and when it matters.",
                      "Define the guarantee first, then state the practical executor boundary.",
                      "State that Send means the future can move across threads safely, then tie it to multithreaded executors.",
                      "A Future is Send if it can be moved between threads safely while suspended. You need it when spawning onto a multithreaded executor like the default Tokio runtime; you do not need it for strictly single-threaded local execution.",
                      "note_future_send"),
        no_tool_trace("You are a Rust education assistant who explains ownership tradeoffs briefly.",
                      "Why is Rc not Send in Rust?",
                      "Explain why Rc is not thread-safe.",
                      "Connect reference-count mutation to thread safety in one short explanation.",
                      "Point out that Rc updates shared refcounts without atomic operations, which is fine on one thread but unsafe across threads.",
                      "Rc is not Send because its reference count is updated non-atomically, so moving it across threads could race and corrupt the count. Use Arc when shared ownership must cross thread boundaries.",
                      "note_rc_send"),
        no_tool_trace("You are a practical Rust mentor who answers in short paragraphs.",
                      "When should I prefer PathBuf over String for filesystem paths in Rust?",
                      "Explain when PathBuf is the better choice for paths.",
                      "Tie the recommendation to semantics and platform correctness.",
                      "Emphasize that paths are not just text and should use path-specific types when code manipulates filesystem locations.",
                      "Prefer PathBuf when the value represents a filesystem path, especially if you will join, normalize, or pass it to file APIs. It models platform path semantics correctly, whereas String is just text.",
                      "note_pathbuf"),
        no_tool_trace("You are a concise systems explainer.",
                      "What problem do Arc and Mutex solve together in Rust?",
                      "Explain what Arc<Mutex<T>> enables.",
                      "State the ownership and synchronization pieces separately, then combine them.",
                      "Describe Arc as shared ownership across threads and Mutex as coordinated mutable access to the inner value.",
                      "Arc<Mutex<T>> gives multiple threads shared ownership of the same value while ensuring only one thread mutates it at a time. Arc solves ownership sharing; Mutex solves synchronized interior mutability.",
                      "note_arc_mutex"),
        no_tool_trace("You are a concise engineering explainer.",
                      "Why do long-lived Git branches create so many merge conflicts on small teams?",
                      "Explain the main cause of frequent merge conflicts.",
                      "Tie conflicts to delayed integration and overlapping edits.",
                      "Keep the explanation centered on long-lived divergence and multiple people editing the same areas before integrating.",
                      "Long-lived branches create more merge conflicts because they let code drift farther from main while multiple people keep editing the same files. The longer work stays unintegrated, the more likely those edits collide when you finally merge.",
                      "note_git_conflicts"),
        no_tool_trace("You are a concise architecture reviewer.",
                      "Why are rollout plans safer when they move low-risk services first?",
                      "Explain why staged rollout order matters.",
                      "Connect rollout order to blast radius and learning.",
                      "State that early low-risk migrations surface hidden assumptions before the riskiest cutovers.",
                      "Starting with low-risk services reduces blast radius and lets the team discover tooling, networking, and observability problems before touching critical workloads. It turns the first migrations into learning steps instead of existential bets.",
                      "note_rollout_order"),
        no_tool_trace("You are a concise data engineering mentor.",
                      "Why should production schema changes use migrations instead of creating tables at app startup?",
                      "Explain the operational reason for migrations.",
                      "Center the answer on explicitness, repeatability, and safety.",
                      "Keep the explanation about reviewable state changes and safer deploys.",
                      "Use migrations in production because they make schema changes explicit, reviewable, and repeatable across environments. Startup-created tables are convenient for prototypes, but they hide change history and make coordinated deploys riskier.",
                      "note_migrations"),
        no_tool_trace("You are a concise systems mentor.",
                      "Why do flaky tests often come from hidden time or concurrency assumptions?",
                      "Explain the main source of flakiness.",
                      "Connect nondeterminism to scheduling, timing, and shared state.",
                      "Keep it focused on tests depending on events that do not happen in a fixed order every run.",
                      "Flaky tests often depend on timing or scheduling that is not deterministic, such as background tasks, retries, shared state, or race-prone setup. When a test assumes a precise order or latency budget, small runtime differences can make it pass sometimes and fail other times.",
                      "note_flaky_tests"),
        no_tool_trace("You are a concise reliability explainer.",
                      "What is the operational risk of using broad allow rules to silence clippy warnings?",
                      "Explain why broad lint suppression is risky.",
                      "Tie it to hiding future regressions.",
                      "Keep the answer short and emphasize that broad suppression makes future bad patterns invisible.",
                      "Broad allow rules hide both the current warning and similar future regressions, so the codebase loses signal right where the team wanted safety feedback. It is safer to suppress a specific lint narrowly or fix the root cause.",
                      "note_clippy_allow"),
    ])

    rust_doc_items = [
        ("std::mem::take", "Look up std::mem::take in the docs tool.", "Explain what it does briefly.", "Use one tool call, then summarize the behavior and Default requirement.", "std::mem::take", "Replaces a value behind a mutable reference with Default::default() and returns the previous value.", "Use the doc wording directly and mention the Default requirement.", "std::mem::take replaces the value behind a mutable reference with Default::default() and returns the old value, so the type must implement Default."),
        ("Option::take", "Look up Option::take in the docs tool.", "Explain what it does briefly.", "Use one tool call, then summarize the move-out behavior.", "Option::take", "Takes the value out of the option, leaving None in its place.", "State that it moves the contents out and leaves None behind.", "Option::take moves the current value out of an Option and leaves None behind, which is handy for taking ownership from a field safely."),
        ("Iterator::fold", "Look up Iterator::fold in the docs tool.", "Explain the accumulator behavior briefly.", "Use one tool call, then summarize the fold contract.", "Iterator::fold", "Takes an initial accumulator and applies a closure to the accumulator and each element to produce one final value.", "Describe fold as repeated accumulation into one value.", "Iterator::fold reduces an iterator to one final value by repeatedly applying a closure to an accumulator, starting from an initial value."),
        ("Vec::with_capacity", "Look up Vec::with_capacity in the docs tool.", "Explain its effect on allocation briefly.", "Use one tool call, then summarize capacity versus length.", "Vec::with_capacity", "Creates a new, empty Vec with at least the specified capacity.", "Point out that length stays zero while capacity is preallocated.", "Vec::with_capacity creates an empty vector with preallocated space for at least that many elements, which can reduce reallocations; the length is still zero until you push items."),
        ("std::borrow::Cow", "Look up std::borrow::Cow in the docs tool.", "Explain owned versus borrowed behavior briefly.", "Use one tool call, then summarize clone-on-write semantics.", "std::borrow::Cow", "A clone-on-write smart pointer that can hold borrowed or owned data and clones into owned form only when needed.", "Explain that it avoids allocation until mutation or ownership is required.", "Cow lets APIs accept either borrowed or owned data without forcing an allocation up front; it only clones into owned data if mutation or ownership is needed."),
        ("AsRef", "Look up AsRef in the docs tool.", "Explain the reference-conversion role briefly.", "Use one tool call, then summarize the cheap conversion behavior.", "AsRef", "A trait for cheap reference-to-reference conversion via as_ref(&self) -> &T.", "Describe it as a lightweight borrowed conversion trait.", "AsRef is a trait for cheap borrowed conversion: it lets a value be viewed as a reference to another type, which is useful for accepting flexible input types without allocating."),
        ("Box::pin", "Look up Box::pin in the docs tool.", "Explain why pinning matters briefly.", "Use one tool call, then summarize the heap pinning behavior.", "Box::pin", "Allocates a value on the heap and pins it so it will not move.", "Mention that pinning is useful when movement would break invariants.", "Box::pin places a value on the heap and pins it so it can no longer move, which is useful for async or self-referential patterns that rely on stable addresses."),
        ("std::mem::drop", "Look up std::mem::drop in the docs tool.", "Explain what happens to the value briefly.", "Use one tool call, then summarize the ownership-taking behavior.", "std::mem::drop", "Takes ownership of a value and runs its destructor immediately.", "State that drop consumes the value and runs Drop now rather than later.", "std::mem::drop takes ownership of a value and runs its destructor immediately, so the value is consumed and cannot be used afterward."),
        ("BTreeMap", "Look up BTreeMap in the docs tool.", "Explain when it is preferable briefly.", "Use one tool call, then summarize the ordering tradeoff.", "BTreeMap", "Keeps keys ordered and is useful for range queries and deterministic iteration.", "Tie the recommendation to key ordering and range access.", "Choose BTreeMap when key ordering or range queries matter more than average-case hash lookup speed, since it maintains keys in sorted order."),
        ("tokio::sync::Mutex", "Look up tokio::sync::Mutex in the docs tool.", "Explain the async-specific caveat briefly.", "Use one tool call, then summarize the executor-friendly behavior.", "tokio::sync::Mutex", "An async-aware mutex whose lock is acquired with .await; avoid holding the guard across unrelated awaits for long periods.", "Highlight that it coordinates async tasks without blocking the thread.", "tokio::sync::Mutex is an async-aware mutex for coordinating mutable access in async code; it avoids blocking the thread, but you should still keep lock guards short-lived."),
    ]
    for symbol, todo1, todo2, rationale, arg_symbol, result_data, think, response in rust_doc_items:
        traces.append(
            single_tool_trace(
                "You are a Rust documentation assistant who answers briefly and precisely.",
                rustdoc,
                f"In Rust, what does {symbol} do? Use the docs tool." if symbol not in {"BTreeMap", "AsRef", "tokio::sync::Mutex"} else (
                    "When would you choose BTreeMap over HashMap in Rust? Use the docs tool." if symbol == "BTreeMap" else
                    "What does the trait AsRef do in Rust? Use the docs tool." if symbol == "AsRef" else
                    "What should I remember about tokio::sync::Mutex in async Rust? Use the docs tool."
                ),
                [todo1, todo2],
                rationale,
                "rustdoc_lookup",
                [("symbol", arg_symbol)],
                "res1",
                result_data,
                think,
                "note1",
                response,
            )
        )

    rust_debug_items = [
        ("My Rust crate fails to compile after I changed a function to use `?` on a `Result`. I’m not sure what trait or type I need to add to make error conversion work.",
         "cargo check: error[E0277]: `?` couldn't convert the error to `MyError`; the trait `From<std::io::Error>` is not implemented for `MyError`.",
         "FromResidual",
         "For Result, `?` requires a conversion path from the source error into the function's return error type, commonly via `From<E>`.",
         "The compiler is telling you that `?` needs to turn `std::io::Error` into `MyError`, but no conversion exists. Fix it by implementing `From<std::io::Error> for MyError`, changing the function’s return type to one that already accepts that error, or wrapping the call with an explicit map_err."),
        ("My Rust project fails to compile after I changed a function to return an iterator. The error says it cannot return a value referencing a local variable.",
         "cargo check: error[E0515]: cannot return value referencing local variable `v`; use `.into_iter()` to return an iterator that owns its items, or move the owned value out.",
         "impl Trait return lifetime iterator",
         "This usually means the iterator borrows from a local value that will be dropped before the caller can use it.",
         "You are probably returning an iterator that borrows from a local collection, so the borrow would outlive the collection. A clean fix is to return an owning iterator (for example via `into_iter()`), return the owned collection instead, or make the iterator borrow from data owned by the caller instead of a local temporary."),
        ("My Rust crate started failing tests with a borrow checker error around iterators. Tests are flaky locally. Can you quickly triage and suggest the most likely fix direction?",
         "error[E0502]: cannot borrow `items` as mutable because it is also borrowed as immutable; the loop iterates items.iter() and then calls items.push(...).",
         "Iterator::iter",
         "The compiler output already points to mutating a collection while iterating it immutably.",
         "The likely issue is mutating the same collection while holding an immutable iterator over it. Fix direction: collect the new values separately, iterate over a cloned snapshot, or restructure the loop so mutation happens after iteration instead of inside it."),
        ("My tests hang in CI and I suspect a deadlock around Mutex + async. Clippy isn’t available here—what should I check and how can I narrow it down quickly?",
         "Error: cargo clippy unavailable on this toolchain",
         "tokio::sync::Mutex",
         "Use one docs fallback and then give concrete checks about locks held across await points.",
         "First check whether any task holds a mutex guard across an `.await`, because that is a common async deadlock pattern. Then look for inconsistent lock ordering and blocking calls inside critical sections; if you can, add logging around lock acquisition/release to find the task that never lets go."),
        ("My Rust helper won’t compile after I tried to store different iterator types in one Vec. What’s going on and what’s a clean fix?",
         "cargo check: error[E0308]: expected `Map<_, _>`, found `Filter<_, _>` when pushing into `Vec`; each iterator adapter has a distinct concrete type.",
         "dyn Iterator",
         "Explain that iterator adapters have different concrete types even if they share the same trait.",
         "You are trying to store different concrete iterator adapter types in one Vec, but each adapter has its own distinct type. A clean fix is to box them as `Box<dyn Iterator<Item = T>>`, use an enum wrapper if the set is fixed, or collect to concrete data before storing."),
        ("My Rust unit test fails after sorting a Vec<f32>; it expects stable ordering when values are equal or NaN. What’s going on and what’s a clean fix?",
         "test panic: comparator uses `a.partial_cmp(b).unwrap()`; Expected NaNs at end and stable order for equal values.",
         "slice::sort_by / f32::total_cmp",
         "Point out that NaN breaks partial_cmp-based assumptions and total ordering must be explicit.",
         "The problem is that `f32::partial_cmp` returns None for NaN, so unwrapping it is invalid and the comparator is not a total order. Use `total_cmp` for deterministic float ordering, and if equal-value stability matters, use a stable sort or add a tie-breaker key."),
        ("My Rust crate won’t compile after I tried to store a closure capturing a local reference in a struct for later use. Explain what’s wrong and how to fix it.",
         "cargo check: error[E0597]: `local` does not live long enough; closure may outlive the current function, but it borrows `local`.",
         "FnOnce + 'static",
         "Explain that the closure outlives the borrowed local and must own its captures or be tied to a shorter lifetime.",
         "The closure is trying to outlive a borrowed local reference, so the compiler rejects it. Fix it by moving owned data into the closure, parameterizing the struct with an explicit lifetime if the borrow truly must be external, or redesigning the API so the closure does not escape the scope of the borrowed value."),
        ("My Rust function returns a reference to a local String and now the compiler complains. What is it objecting to and what is the right fix?",
         "cargo check: error[E0515]: cannot return reference to local variable `s`.",
         "lifetime elision",
         "Keep the explanation focused on returning a borrow to data that will be dropped at function exit.",
         "The compiler is objecting because the returned reference would point to a local value that is destroyed when the function returns. The fix is to return an owned `String`, borrow from caller-owned data instead, or redesign the API so the referenced data lives long enough."),
        ("Clippy is failing in CI with an error about an unknown lint name; the clippy tool might be unavailable. Give concise guidance.",
         "Error: cargo clippy output unavailable",
         "unknown_lints",
         "Use one docs fallback and explain the common version-mismatch cause.",
         "An unknown lint name usually means a Clippy/Rust version mismatch or a renamed/removed lint. Check the toolchain version used in CI, update or remove the stale lint name, and only use `allow(unknown_lints)` as a temporary unblock while you align versions."),
        ("My Rust CLI parses args with clap and fails to compile after I added a `Vec<&str>` field to the config struct. Diagnose the likely issue and give a concise fix.",
         "cargo check: error[E0106]: missing lifetime specifier; error[E0521]: borrowed data escapes outside of function when returning `Vec<&str>` from clap parsing.",
         "clap derive String vs &str",
         "Explain that clap-parsed values should generally be stored as owned Strings rather than borrowed &str fields.",
         "The likely issue is that your config struct is trying to store borrowed strings from parsing, but those borrows do not outlive the parsing scope. Use `Vec<String>` (or another owned type like `PathBuf`) in the config instead of `Vec<&str>` unless you are explicitly threading lifetimes through the whole type."),
    ]
    for i, (user, check_result, doc_symbol, think, response) in enumerate(rust_debug_items):
        traces.append(
            multi_tool_trace(
                "You are a Rust debugging assistant who diagnoses compiler and tool output concisely.",
                cargo,
                user,
                [
                    "Get the primary diagnostic or tool output for the failure.",
                    "Use one targeted docs lookup if it sharpens the fix.",
                    "Give a concise diagnosis and repair direction.",
                ],
                "Use one concrete tool result, optionally one supporting lookup, then answer without extra loops.",
                "cargo_check" if "compile" in user or "compiler" in user or "Clippy" not in user and "tests hang" not in user and "unit test fails" not in user else ("cargo_clippy" if "Clippy" in user or "clippy" in user else "cargo_test"),
                [("crate_path", "./")] if "filter" not in check_result else [("crate_path", "./"), ("filter", "sort_floats")],
                "step1",
                check_result,
                think,
                "note1",
                "rustdoc_lookup",
                [("symbol", doc_symbol)],
                "step2",
                f"rustdoc: {doc_symbol} guidance relevant to this failure.",
                "The tool outputs are enough to anchor a short fix direction; stop after the answer.",
                "note2",
                response,
            )
        )

    ci_items = [
        ("Our nightly integration tests started timing out in the container startup phase. What should I check first?",
         "Error: CI log service unavailable",
         "test-runner",
         "Cached incident note: timeouts commonly occur when the container never becomes ready due to a failing healthcheck or slow image pull from the registry.",
         "Check container readiness first: image pull latency/auth, the startup healthcheck itself, and any recent CPU or memory limit changes that would delay boot. This recommendation is based on the cached incident note because live logs were unavailable."),
        ("Our deploy pipeline started failing at the unit-tests stage after a dependency bump. What should I check first?",
         "Run: 18422; FAIL: Cannot find module `left-pad` in test/bootstrap.js after dependency bump.",
         "Cannot find module left-pad",
         "1 match: repo/test/bootstrap.js imports `left-pad` directly.",
         "Start with the first failing import in the unit-test logs: the dependency bump likely changed a package name or entrypoint. Check the import in test/bootstrap.js, verify the lockfile changed consistently, and pin or revert the bump if you need a quick unblock."),
        ("Our integration tests intermittently time out only on main branch runs. What should we look at first?",
         "Error: CI log service unavailable",
         "ci",
         "Cached incident note: main-branch timeouts frequently traced to runner pool saturation and occasional DNS failures during dependency setup.",
         "First check whether main runs are landing on more saturated runners or a different runner class, then verify DNS/network reliability during dependency setup. The main-only pattern makes infrastructure skew more likely than a deterministic test bug."),
        ("Our deploys to staging fail intermittently with a permission denied error. Where should we look first?",
         "Staging deploy job failed while fetching secret staging/DB_PASSWORD; runner role missing `secrets.read`.",
         "staging-deploy",
         "Cached incident note: similar failures came from a policy rollout that removed secret read access in one namespace.",
         "Look first at the deploy runner’s IAM or service-account permissions for the secrets backend. The logs already point to denied secret access, so confirm the runner role and namespace policy before investigating app code."),
        ("Our nightly pipeline started failing after a merge, but reruns usually pass. What should I check first?",
         "Error: CI log service returned 503",
         "pipeline",
         "Cached incident note: flaky nightly failures that pass on rerun are frequently caused by transient dependency resolution or external registry hiccups.",
         "Check whether the failure happens during dependency or artifact fetches and whether versions are pinned. If reruns usually pass, transient external fetches or unpinned dependencies are a stronger first suspect than deterministic code regressions."),
    ]
    for user, log_result, service, cache_result, response in ci_items:
        traces.append(
            multi_tool_trace(
                "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
                ci_tools,
                user,
                [
                    "Pull the most relevant recent logs or failure output.",
                    "Use one fallback source only if the primary source fails or is insufficient.",
                    "Provide the first concrete investigation angle.",
                ],
                "Start with direct evidence, use one fallback at most, then answer succinctly.",
                "get_ci_logs",
                [("run_id", "main-failing-run-18422" if "main" in user else "nightly-failing-run-18422")],
                "logs1",
                log_result,
                "If live logs fail or are too thin, use one fallback source to avoid over-searching.",
                "note_logs",
                "fetch_cached_incident" if "Cannot find module" not in log_result else "code_search",
                [("service", service)] if "Cannot find module" not in log_result else [("query", "left-pad")],
                "aux1",
                cache_result,
                "Use the second tool result to sharpen one focused next step, then stop.",
                "note_aux",
                response,
            )
        )

    misc = [
        single_tool_trace("You are a data access assistant who uses SQL and answers briefly.", sql_tools,
                          "How many paid subscriptions were canceled yesterday?",
                          ["Query the cancellation count.", "Answer with the count briefly."],
                          "Use one SQL query, then respond with the returned count.",
                          "run_sql", [("query", "SELECT COUNT(*) AS canceled_paid_subscriptions_yesterday FROM subscriptions WHERE status = 'canceled' AND plan_type = 'paid' AND canceled_at >= CURRENT_DATE - INTERVAL '1 day' AND canceled_at < CURRENT_DATE;")],
                          "res1", "Query result: canceled_paid_subscriptions_yesterday = 42.",
                          "The SQL result already contains the exact number needed for the answer.", "note1",
                          "There were 42 paid subscriptions canceled yesterday."),
        single_tool_trace("You are a calculation assistant who returns precise numeric answers with a short explanation.", [tool("calculator", "Evaluates a math expression.", param("expression", "string", "Expression to evaluate"))],
                          "A jacket was $120, now it’s $90. What percent discount is that? Use the calculator.",
                          ["Compute the percent discount.", "Answer with the percentage briefly."],
                          "Use the calculator once, then state the computed percentage.",
                          "calculator", [("expression", "((120-90)/120)*100")], "res1", "((120-90)/120)*100 = 25",
                          "Convert the calculator result into a concise percent statement.", "note1",
                          "The discount is 25%."),
        multi_tool_trace("You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.", math_tools,
                         "Compute the indefinite integral of (x^3 - 2*x)/(x^2 + 1). Verify it by differentiation and keep the answer concise.",
                         ["Compute an antiderivative.", "Verify it by differentiation.", "State the final answer briefly."],
                         "Use one symbolic solve step, one derivative check, then stop.",
                         "solve_symbolic", [("expression", "(x^3 - 2*x)/(x^2 + 1)"), ("operation", "integrate"), ("variable", "x")], "int1",
                         "Computed antiderivative: (x^2 - 3*ln(x^2 + 1))/2 + C",
                         "The antiderivative is already compact; verify it directly rather than adding extra steps.", "note1",
                         "derivative_check", [("candidate_antiderivative", "(x^2 - 3*ln(x^2 + 1))/2"), ("target_expression", "(x^3 - 2*x)/(x^2 + 1)"), ("variable", "x")], "chk1",
                         "Derivative matches the target exactly.",
                         "The derivative check confirms correctness, so the final answer can stay short.", "note2",
                         "Antiderivative: (x^2 - 3 ln(x^2 + 1))/2 + C. The derivative check matches the integrand exactly."),
        single_tool_trace("You are a document assistant who reads a file and returns a short, concrete summary.", file_tools,
                          "Open /docs/q3_launch_postmortem.md and summarize the main takeaways and action items.",
                          ["Load the requested document excerpt.", "Summarize the main takeaways and action items."],
                          "Use the file tool once, then condense the excerpt into a short summary.",
                          "load_file", [("path", "/docs/q3_launch_postmortem.md")], "res1",
                          "Excerpt: Launch slipped 2 weeks due to late scope changes and unclear ownership. Incident detection lagged because dashboards lacked error-rate alerts. Action items: scope freeze, one DRI per workstream, pre-launch load testing, expanded dashboards and an on-call runbook.",
                          "Extract the delay cause, monitoring gap, and concrete action items into one tight summary.", "note1",
                          "Main takeaways: late scope changes and unclear ownership delayed the launch, and weak alerting slowed incident detection. Action items: add scope freeze/change control, assign one DRI per workstream, run pre-launch load tests, and strengthen dashboards plus the on-call runbook."),
        multi_tool_trace("You are a planning assistant that helps product teams build realistic launch plans and concise schedules.", plan_tools,
                         "We need a 3-week rollout plan for an in-app onboarding checklist update. Pull major tasks, confirm the team can staff it, and keep it concise.",
                         ["Check team availability for the 3-week window.", "Generate a baseline work breakdown.", "Provide a concise schedule recommendation."],
                         "Get staffing first, then a minimal work breakdown, then summarize feasibility.",
                         "get_availability", [("team_list", "ava,ben,chen,dina"), ("start_date", "2026-07-06"), ("end_date", "2026-07-26")], "avail1",
                         "Availability: ava 60%, ben 40%, chen 70%, dina 50% for the 3-week window.",
                         "Availability looks workable; now get a minimal breakdown sized to the short timeline.", "note1",
                         "create_project_plan", [("project_name", "in-app onboarding checklist update"), ("objectives", "ship updated checklist copy, triggers, analytics, and QA"), ("timeline_weeks", "3")], "plan1",
                         "Plan ID plan_onb_v1: requirements and copy, trigger logic, UI updates, analytics events, QA and rollout.",
                         "With staffing and tasks in hand, give a simple sequencing recommendation instead of adding more tool steps.", "note2",
                         "The team can likely cover this in 3 weeks if work starts with requirements/copy, then trigger logic and UI in parallel, followed by analytics wiring and a short QA/rollout window."),
        multi_tool_trace("You are a Git assistant who gives compact, practical guidance.", git_tools,
                         "My PR branch won't push because it says non-fast-forward. I don't want to lose my local commits. What should I do?",
                         ["Inspect repo state to confirm divergence.", "Inspect recent history to understand local vs remote commits.", "Provide a safe integration sequence that preserves local work."],
                         "Check branch state, check recent commits, then recommend a safe rebase-or-merge path.",
                         "git_status", [("repo_path", "./")], "st1",
                         "On branch feature/pr-42. Your branch and origin/feature/pr-42 have diverged, and have 3 and 2 different commits each. Working tree clean.",
                         "The branch has diverged, so check recent local and remote commits before recommending the next command.", "note1",
                         "git_log", [("repo_path", "./"), ("limit", "8")], "log1",
                         "local HEAD: abc1234 Add validation for empty inputs; bcd2345 Refactor request parsing. origin/feature/pr-42: def4567 Fix CI by pinning action versions; efg5678 Adjust lint config.",
                         "With divergence confirmed, recommend fetch plus rebase as the safest default when local commits must be preserved.", "note2",
                         "Fetch the remote branch, then rebase your local commits on top of it so you keep your work while integrating the remote changes. If conflicts appear, resolve them commit by commit, run tests, then push the rebased branch (usually with --force-with-lease)."),
    ]
    traces.extend(misc)

    traces.extend([
        no_tool_trace("You are a Rust language assistant who gives concise ownership explanations.",
                      "Why does `collect::<Vec<_>>()` sometimes fix type inference errors in Rust?",
                      "Explain why adding a concrete collection type can resolve inference ambiguity.",
                      "Connect the fix to the compiler needing a concrete destination type.",
                      "State that collect needs to know what collection to build, and explicit type information removes the ambiguity.",
                      "Adding `collect::<Vec<_>>()` gives the compiler a concrete target collection type, which resolves ambiguity when it cannot infer what `collect` should produce from context alone.",
                      "note_collect_vec"),
        no_tool_trace("You are a Rust API design assistant who answers briefly.",
                      "Why is `String` usually a better struct field type than `&str` in application config types?",
                      "Explain why owned strings are usually safer in config structs.",
                      "Tie the answer to lifetime simplicity and ownership boundaries.",
                      "Keep it focused on config values often needing to outlive the parsing context.",
                      "String is usually better because config structs often need to own their data after parsing, serialization, or movement across layers. Using `&str` pushes lifetimes through the whole type and is only worth it when you clearly have long-lived backing storage.",
                      "note_string_field"),
        single_tool_trace("You are a Rust documentation assistant who answers briefly and precisely.", rustdoc,
                          "In Rust, what does `Iterator::collect` do? Use the docs tool.",
                          ["Look up Iterator::collect in the docs tool.", "Explain it briefly."],
                          "Use the docs tool once, then summarize the behavior and type requirement.",
                          "rustdoc_lookup", [("symbol", "Iterator::collect")], "res1",
                          "Transforms an iterator into a collection or other type that implements FromIterator.",
                          "State that collect consumes the iterator and needs a destination type implementing FromIterator.", "note1",
                          "Iterator::collect consumes an iterator and builds a target type from it, as long as that target implements FromIterator."),
        single_tool_trace("You are a Rust documentation assistant who answers briefly and precisely.", rustdoc,
                          "What does `HashMap::entry` help with in Rust? Use the docs tool.",
                          ["Look up HashMap::entry in the docs tool.", "Explain its main use briefly."],
                          "Use the docs tool once, then summarize the lookup-or-insert pattern.",
                          "rustdoc_lookup", [("symbol", "HashMap::entry")], "res1",
                          "Provides in-place manipulation of a value in the map for a given key, including insert-if-missing patterns.",
                          "Describe entry as the API for update-or-insert without double lookup.", "note1",
                          "HashMap::entry lets you inspect, insert, or update a key in one pass, which is especially useful for counters and insert-if-missing logic."),
        single_tool_trace("You are a data access assistant who uses SQL and answers briefly.", sql_tools,
                          "What percentage of new signups in the last 30 days came from organic search?",
                          ["Query total signups and organic-search signups.", "Compute and report the percentage briefly."],
                          "Use one SQL query, then state the computed share.",
                          "run_sql", [("query", "SELECT COUNT(*) AS total_signups, SUM(CASE WHEN acquisition_channel = 'organic_search' THEN 1 ELSE 0 END) AS organic_signups FROM signups WHERE created_at >= (CURRENT_DATE - INTERVAL '30 days');")],
                          "res1", "Query result: total_signups=4120, organic_signups=1175.",
                          "Convert the totals into a percentage and present it briefly.", "note1",
                          "Organic search accounts for 28.5% of new signups over the last 30 days."),
        single_tool_trace("You are a calculation assistant who returns precise numeric answers with a short explanation.", [tool("calculator", "Evaluates a math expression.", param("expression", "string", "Expression to evaluate"))],
                          "Revenue grew from $420k to $693k. What is the percentage increase? Use the calculator.",
                          ["Compute the percentage increase.", "Report the increase briefly."],
                          "Use the calculator once, then translate the result into a concise percentage statement.",
                          "calculator", [("expression", "((693-420)/420)*100")], "res1", "((693-420)/420)*100 = 65.00",
                          "State the increase directly from the calculator output without extra filler.", "note1",
                          "The revenue increase is 65.00%."),
        multi_tool_trace("You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.", math_tools,
                         "Differentiate x^4 * ln(x), then verify the derivative by a second tool step and keep the answer concise.",
                         ["Differentiate the expression.", "Verify the derivative by a second tool step.", "State the final derivative briefly."],
                         "Use one differentiation step, one verification step, then stop.",
                         "solve_symbolic", [("expression", "x^4 * ln(x)"), ("operation", "differentiate"), ("variable", "x")], "d1",
                         "Computed derivative: 4*x^3*ln(x) + x^3",
                         "The derivative result is already simple; verify it rather than adding another transform.", "note1",
                         "derivative_check", [("candidate_antiderivative", "(x^4*ln(x))"), ("target_expression", "4*x^3*ln(x) + x^3"), ("variable", "x")], "chk1",
                         "Differentiating x^4*ln(x) yields 4*x^3*ln(x) + x^3.",
                         "The verification matches, so the final answer can just state the derivative cleanly.", "note2",
                         "The derivative is 4x^3 ln(x) + x^3."),
        single_tool_trace("You are a document assistant who reads a file and returns a short, concrete summary.", file_tools,
                          "Open /docs/security_audit_apr.md and summarize the top three findings.",
                          ["Load the requested document excerpt.", "Summarize the top findings briefly."],
                          "Use the file tool once, then condense the excerpt into a short findings summary.",
                          "load_file", [("path", "/docs/security_audit_apr.md")], "res1",
                          "Excerpt: incomplete MFA enforcement for legacy admin accounts, critical dependencies missing recent security patches, and gaps in centralized logging/alerting that hinder incident response.",
                          "Extract the three concrete findings directly and keep the wording brief.", "note1",
                          "Top findings: MFA is incomplete for legacy admin accounts, critical dependencies are behind on security patches, and centralized logging/alerting is too weak for reliable incident response."),
        multi_tool_trace("You are a planning assistant that helps product teams build realistic launch plans and concise schedules.", plan_tools,
                         "We need a 4-week launch plan for a billing export CSV improvement. Check team availability, generate the task breakdown, and keep the final recommendation concise.",
                         ["Check team availability for the 4-week window.", "Generate the task breakdown.", "Provide a concise schedule recommendation."],
                         "Get staffing first, then a baseline task breakdown, then stop with a short recommendation.",
                         "get_availability", [("team_list", "maya,liam,noor,oscar"), ("start_date", "2026-08-04"), ("end_date", "2026-09-01")], "avail1",
                         "Availability: maya 70%, liam 50%, noor 80%, oscar 40% for the 4-week window.",
                         "Availability is enough to scope the next planning step; now get a compact work breakdown.", "note1",
                         "create_project_plan", [("project_name", "billing export CSV improvement"), ("objectives", "fix column consistency, header naming, duplicate handling, and rollout docs"), ("timeline_weeks", "4")], "plan1",
                         "Plan ID plan_csv_v1: requirements and field audit, export generator changes, duplicate handling, QA with sample customers, rollout docs.",
                         "With staffing and tasks available, the final answer should just recommend a simple sequence.", "note2",
                         "The team can likely deliver this in 4 weeks by starting with requirements and field audit, then export-generator changes, followed by duplicate handling, QA, and a short rollout-docs finish.")
    ])

    assert len(traces) == 50, len(traces)
    return traces


def main() -> int:
    traces = records()
    bad: list[tuple[int, list[str]]] = []
    with OUT.open("w") as f:
        for i, trace in enumerate(traces, start=1):
            res = validate_trace(trace)
            if not res.valid:
                bad.append((i, res.errors))
            f.write(json.dumps({"trace": trace}, ensure_ascii=False) + "\n")
    print(json.dumps({"count": len(traces), "output": str(OUT), "invalid": bad}, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
