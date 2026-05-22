#!/usr/bin/env python3
"""Build a rust-skewed held-out formal eval set with exact-overlap checks.

Covers conceptual Rust, rustdoc lookups, cargo diagnostics, incident triage,
file summarization, planning, AND the dev-tool stack the RL env exercises
(read_file / apply_patch / cargo_check / cargo_build / cargo_run / cargo_test
/ rustc). Eval prompts use /srv/eval/* paths so they never collide with the
SFT pool's /workspace/glyph/runs/* paths."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "synthetic_data/gold_glyph_3000.jsonl"
OUTPUT_PATH = ROOT / "sft/evals/prompts_125.yaml"


def rustdoc_tool() -> list[dict]:
    return [{
        "name": "rustdoc_lookup",
        "description": "Returns concise documentation for a Rust symbol.",
        "params": {"symbol": {"type": "string", "description": "Rust symbol"}},
    }]


def cargo_tools() -> list[dict]:
    return [
        {
            "name": "cargo_check",
            "description": "Runs cargo check on a Rust crate and returns the main compiler diagnostics.",
            "params": {"crate_path": {"type": "string", "description": "Path to the crate", "required": False}},
        },
        {
            "name": "rustdoc_lookup",
            "description": "Returns concise documentation for a Rust type, trait, macro, or function.",
            "params": {"symbol": {"type": "string", "description": "Rust symbol to look up", "required": False}},
        },
    ]


def incident_tools() -> list[dict]:
    return [
        {
            "name": "get_ci_logs",
            "description": "Fetches CI logs for a run.",
            "params": {"run_id": {"type": "string", "description": "Run id"}},
        },
        {
            "name": "code_search",
            "description": "Searches the codebase.",
            "params": {"query": {"type": "string", "description": "Search query"}},
        },
        {
            "name": "fetch_cached_incident",
            "description": "Returns a cached incident note.",
            "params": {"service": {"type": "string", "description": "Service name"}},
        },
    ]


def load_file_tool() -> list[dict]:
    return [{
        "name": "load_file",
        "description": "Loads a file from disk and returns a short excerpt.",
        "params": {"path": {"type": "string", "description": "Path to load"}},
    }]


def rust_dev_tools() -> list[dict]:
    """Mirrors rl/rust/tools.py — the schema the RL env actually executes."""
    return [
        {
            "name": "read_file",
            "description": "Reads a file from disk and returns its contents.",
            "params": {"file_path": {"type": "string", "description": "Path to the file to read"}},
        },
        {
            "name": "apply_patch",
            "description": "Applies a textual find/replace edit to a single file. 'find' must occur exactly once.",
            "params": {
                "file_path": {"type": "string", "description": "Path to the file to edit"},
                "find": {"type": "string", "description": "Exact text snippet to locate"},
                "replace": {"type": "string", "description": "Replacement text"},
            },
        },
        {
            "name": "cargo_check",
            "description": "Runs cargo check to verify code compiles without producing a binary.",
            "params": {"project_path": {"type": "string", "description": "Cargo project directory"}},
        },
        {
            "name": "cargo_build",
            "description": "Compiles the Cargo project into binaries.",
            "params": {"project_path": {"type": "string", "description": "Cargo project directory"}},
        },
        {
            "name": "cargo_test",
            "description": "Runs the test suite for a Cargo project.",
            "params": {"project_path": {"type": "string", "description": "Cargo project directory"}},
        },
        {
            "name": "cargo_run",
            "description": "Builds and runs the binary of a Cargo project, returning its stdout.",
            "params": {"project_path": {"type": "string", "description": "Cargo project directory"}},
        },
        {
            "name": "rustc",
            "description": "Compiles a single Rust source file to an executable.",
            "params": {
                "source_file": {"type": "string", "description": "Source file"},
                "output": {"type": "string", "description": "Output binary path", "required": False},
            },
        },
    ]


def planning_tools() -> list[dict]:
    return [
        {
            "name": "get_availability",
            "description": "Returns weekly availability by teammate.",
            "params": {
                "team_list": {"type": "string", "description": "Comma-separated IDs", "required": False},
                "start_date": {"type": "string", "description": "Start date", "required": False},
                "end_date": {"type": "string", "description": "End date", "required": False},
            },
        },
        {
            "name": "create_project_plan",
            "description": "Generates a short work breakdown.",
            "params": {
                "project_name": {"type": "string", "description": "Project name", "required": False},
                "objectives": {"type": "string", "description": "Objectives", "required": False},
                "timeline_weeks": {"type": "string", "description": "Timeline in weeks", "required": False},
            },
        },
    ]


def main() -> None:
    prompts: list[dict] = []

    concept_system = "You are a Rust language assistant who gives compact conceptual explanations."
    concept_rows = [
        ("rust_enum_vs_boxed_trait", "In Rust, when is an enum a better fit than storing handlers behind `Box<dyn Trait>`? Give one tradeoff and one rule of thumb."),
        ("rust_option_vs_result_boundary", "In a Rust API, when should a function return `Option<T>` instead of `Result<T, E>`? Give one concrete rule of thumb."),
        ("rust_rc_vs_arc_choice", "In Rust, when would you pick `Rc<T>` over `Arc<T>`? Keep it concise and mention one cost."),
        ("rust_borrow_vs_clone_hot_path", "In Rust, when should you borrow data instead of cloning it in a hot path? Give one practical tradeoff."),
        ("rust_box_dyn_error_boundary", "In Rust application code, when is `Box<dyn Error>` acceptable, and when is a concrete error type better?"),
        ("rust_impl_trait_vs_generic_arg", "In Rust, when is `impl Trait` in a function signature preferable to a named generic parameter?"),
        ("rust_string_vs_str_api", "In Rust API design, when should an argument be `&str` instead of `String`? Give one clear reason."),
        ("rust_vec_vs_vecdeque", "In Rust, when would you choose `VecDeque<T>` over `Vec<T>`? Mention one operation that drives the choice."),
        ("rust_slice_vs_vec_param", "In Rust, when should a function take `&[T]` instead of `&Vec<T>`? Give a short rule of thumb."),
        ("rust_associated_type_vs_generic", "In Rust traits, when is an associated type a better fit than a generic type parameter?"),
        ("rust_send_vs_sync", "In Rust, what is the practical difference between `Send` and `Sync`? Answer briefly."),
        ("rust_pin_future_concept", "In async Rust, what problem does `Pin` solve for futures? Keep it conceptual and short."),
        ("rust_cow_when_useful", "In Rust, when is `Cow<'a, str>` a good fit? Mention one reason it can simplify an API."),
        ("rust_phantomdata_why", "In Rust, why would a type include `PhantomData<T>` even if it stores no `T` value?"),
        ("rust_interior_mutability_choice", "In Rust, when is interior mutability the right tool instead of a plain `&mut` API?"),
        ("rust_hashmap_vs_btreemap", "In Rust, when is `BTreeMap` a better fit than `HashMap`? Give one concrete tradeoff."),
        ("rust_asref_vs_borrow_trait", "In Rust generics, when is `AsRef<str>` the right bound instead of `Borrow<str>`? Keep it brief."),
        ("rust_iter_vs_iter_mut_vs_into_iter", "In Rust, what is the practical distinction between `.iter()`, `.iter_mut()`, and `.into_iter()`?"),
        ("rust_owned_vs_borrowed_return", "In Rust, when should a function return an owned value instead of a borrowed reference? Mention one constraint."),
        ("rust_from_vs_tryfrom", "In Rust conversions, when should you implement `From` and when should you implement `TryFrom`?"),
        ("rust_copy_vs_clone_derive", "In Rust, when is it appropriate to derive `Copy` instead of only `Clone`?"),
        ("rust_cell_vs_refcell", "In Rust, when is `Cell<T>` enough, and when do you need `RefCell<T>`?"),
        ("rust_static_lifetime_meaning", "In Rust, what does a `'static` lifetime usually mean in practice? Keep it concise."),
        ("rust_collect_turbofish_reason", "In Rust iterators, when do you need a turbofish on `collect()`? Give one simple example pattern."),
        ("rust_async_move_capture", "In async Rust, why does adding `move` to an async block sometimes fix lifetime complaints?"),
        ("rust_object_safety_rule", "In Rust, what makes a trait object-safe? Give one common thing that breaks object safety."),
        ("rust_error_enum_vs_anyhow", "In Rust, when should a library prefer a custom error enum over `anyhow::Error`?"),
        ("rust_iterators_vs_loops", "In Rust, when is an explicit `for` loop clearer than chaining iterator adapters? Give one rule of thumb."),
    ]
    prompts.extend({"name": n, "system": concept_system, "user": u, "tools": []} for n, u in concept_rows)

    docs_system = "You are a Rust documentation assistant who answers briefly and precisely."
    rustdoc_rows = [
        ("rustdoc_mem_take", "Briefly explain `std::mem::take` in Rust, and use the docs tool before answering."),
        ("rustdoc_mem_replace", "Briefly explain `std::mem::replace` in Rust, and use the docs tool before answering."),
        ("rustdoc_mem_swap", "Briefly explain `std::mem::swap` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_fold", "Briefly explain `Iterator::fold` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_try_fold", "Briefly explain `Iterator::try_fold` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_find_map", "Briefly explain `Iterator::find_map` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_flatten", "Briefly explain `Iterator::flatten` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_inspect", "Briefly explain `Iterator::inspect` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_collect", "Briefly explain `Iterator::collect` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_zip", "Briefly explain `Iterator::zip` in Rust, and use the docs tool before answering."),
        ("rustdoc_vec_retain", "Briefly explain `Vec::retain` in Rust, and use the docs tool before answering."),
        ("rustdoc_vec_splice", "Briefly explain `Vec::splice` in Rust, and use the docs tool before answering."),
        ("rustdoc_option_map", "Briefly explain `Option::map` in Rust, and use the docs tool before answering."),
        ("rustdoc_option_and_then", "Briefly explain `Option::and_then` in Rust, and use the docs tool before answering."),
        ("rustdoc_option_as_deref", "Briefly explain `Option::as_deref` in Rust, and use the docs tool before answering."),
        ("rustdoc_result_map_err", "Briefly explain `Result::map_err` in Rust, and use the docs tool before answering."),
        ("rustdoc_result_inspect_err", "Briefly explain `Result::inspect_err` in Rust, and use the docs tool before answering."),
        ("rustdoc_result_ok_or_else", "Briefly explain `Option::ok_or_else` in Rust, and use the docs tool before answering."),
        ("rustdoc_str_split_once", "Briefly explain `str::split_once` in Rust, and use the docs tool before answering."),
        ("rustdoc_path_join", "Briefly explain `PathBuf::join` in Rust, and use the docs tool before answering."),
        ("rustdoc_arc_make_mut", "Briefly explain `Arc::make_mut` in Rust, and use the docs tool before answering."),
        ("rustdoc_cow_to_mut", "Briefly explain `Cow::to_mut` in Rust, and use the docs tool before answering."),
        ("rustdoc_mem_discriminant", "Briefly explain `std::mem::discriminant` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_peekable", "Briefly explain `Iterator::peekable` in Rust, and use the docs tool before answering."),
        ("rustdoc_iter_once", "Briefly explain `std::iter::once` in Rust, and use the docs tool before answering."),
    ]
    prompts.extend({"name": n, "system": docs_system, "user": u, "tools": rustdoc_tool()} for n, u in rustdoc_rows)

    debug_system = "You are a Rust debugging assistant who diagnoses compiler and tool output concisely."
    debug_rows = [
        ("cargo_error_convert", "A Rust function started using `?`, and cargo check now says the error type cannot be converted. What should I inspect first?"),
        ("cargo_trait_bound_missing", "After adding a generic helper in Rust, cargo check now says a trait bound is missing. What should I verify first?"),
        ("cargo_borrow_of_moved_value", "Cargo check says a Rust value was moved and then borrowed later. What is the first thing you would inspect?"),
        ("cargo_temporary_dropped", "Cargo check reports that a temporary value is dropped while borrowed in Rust. What pattern usually causes this?"),
        ("cargo_mutable_borrow_twice", "A Rust function now fails because it tries to mutably borrow the same value twice. What is the first refactor angle to check?"),
        ("cargo_returned_reference_lifetime", "A Rust helper that returns a reference now fails borrow checking after a refactor. What should I verify first?"),
        ("cargo_future_not_send", "Spawning an async task in Rust now fails because the future is not `Send`. What should I inspect first?"),
        ("cargo_collect_type_inference", "Cargo check cannot infer the target type of a `collect()` call in Rust. What is the most direct fix to check first?"),
        ("cargo_debug_trait_missing", "A Rust struct now fails to compile because `Debug` is missing in a derived context. What should I inspect first?"),
        ("cargo_clone_bound_generic", "A generic Rust helper now fails because `clone` is unavailable on `T`. What should I verify first?"),
        ("cargo_closure_outlives_stack", "Cargo check says a closure may outlive the current function but borrows a local variable. What is the first thing to inspect?"),
        ("cargo_object_safety_error", "Turning a Rust trait into `dyn Trait` now fails object-safety checks. What should I inspect first?"),
        ("cargo_recursive_type_size", "A recursive Rust type now fails because the compiler says it has infinite size. What is the first fix to consider?"),
        ("cargo_unpin_requirement", "An async Rust refactor now complains that a type cannot be unpinned. What should I inspect first?"),
        ("cargo_iterator_item_mismatch", "Cargo check says an iterator chain in Rust produces the wrong item type for the next adapter. What should I inspect first?"),
        ("cargo_parse_type_annotation", "A Rust parse call now fails because the compiler cannot infer the target type. What should I verify first?"),
        ("cargo_match_arm_type_mismatch", "A Rust `match` expression now fails because the arms have incompatible types. What is the first thing to inspect?"),
        ("cargo_partial_move_pattern", "Cargo check reports a partial move from a struct in Rust. What is the first pattern you would inspect?"),
        ("cargo_impl_future_lifetime", "A Rust function returning `impl Future` now fails with a lifetime complaint after a refactor. What should I inspect first?"),
        ("cargo_method_not_found_trait", "Cargo check says a method is not found on a Rust type even though a trait impl exists. What should I verify first?"),
    ]
    prompts.extend({"name": n, "system": debug_system, "user": u, "tools": cargo_tools()} for n, u in debug_rows)

    incident_system = "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure."
    incident_rows = [
        ("ci_container_boot_timeout", "A CI job now stalls while the test container is booting. What is the first thing you would verify?"),
        ("ci_image_publish_failure", "A deploy pipeline started failing during image publish. What should I check first?"),
        ("ci_cache_miss_regression", "A previously fast CI workflow is suddenly slow because dependencies seem to rebuild every run. What should I verify first?"),
        ("ci_dns_flake_integration", "Integration tests now fail intermittently because a downstream hostname cannot be resolved. What should I inspect first?"),
        ("ci_migration_lock_wait", "A migration step in CI now hangs waiting on a database lock. What should I check first?"),
        ("deploy_healthcheck_timeout", "A new service revision deploys, but rollout stalls because health checks never go green. What should I verify first?"),
        ("worker_backlog_after_release", "After a release, background jobs are backing up and queue latency is rising. What should I inspect first?"),
        ("secret_rotation_auth_fail", "Right after rotating credentials, a production job starts failing authentication. What should I check first?"),
        ("release_artifact_missing", "A release pipeline now fails because the publish step cannot find its build artifact. What should I inspect first?"),
        ("startup_probe_regression", "A service now fails its startup probe after a base-image change. What is the first thing you would verify?"),
    ]
    prompts.extend({"name": n, "system": incident_system, "user": u, "tools": incident_tools()} for n, u in incident_rows)

    file_system = "You are a document assistant who reads a file and returns a short, concrete summary."
    file_rows = [
        ("docs_latency_postmortem", "Open /docs/q4_latency_postmortem.md and summarize the root cause, mitigation, and open follow-ups."),
        ("docs_release_notes_beta", "Open /docs/release_notes_beta.md and summarize the main user-facing changes and any obvious gaps."),
        ("docs_incident_timeline", "Open /docs/incident_2026_04_17.md and summarize the timeline and the top unresolved action items."),
        ("docs_oncall_handoff", "Open /docs/oncall_handoff_week32.md and summarize the most important risks and pending checks."),
        ("docs_schema_migration_plan", "Open /docs/schema_migration_plan.md and summarize the rollout steps and rollback plan."),
        ("docs_search_eval_report", "Open /docs/search_eval_report.md and summarize the strongest gains, regressions, and next questions."),
        ("docs_mobile_launch_readiness", "Open /docs/mobile_launch_readiness.md and summarize the blockers, owners, and launch recommendation."),
    ]
    prompts.extend({"name": n, "system": file_system, "user": u, "tools": load_file_tool()} for n, u in file_rows)

    planning_system = "You are a planning assistant that helps product teams build realistic launch plans and concise schedules."
    planning_rows = [
        ("plan_onboarding_refresh", "We need a concise 3-week rollout plan for a first-run tips refresh. Pull the major tasks, confirm staffing, and keep it brief."),
        ("plan_billing_settings_refresh", "We need a 2-week plan to prepare design review and implementation kickoff for a billing settings refresh. Confirm staffing and keep it concise."),
        ("plan_search_relevance_update", "We need a concise 4-week rollout plan for a search relevance update. Include implementation, validation, launch checks, and team capacity."),
        ("plan_notification_preference_cleanup", "We need a concise 3-week rollout plan for cleaning up notification preference settings. Pull the core tasks and confirm staffing."),
        ("plan_trial_conversion_banner", "We need a 2-week rollout plan for a trial-conversion banner experiment. Include setup, QA, metrics checks, and staffing."),
        ("plan_team_admin_permissions", "We need a concise 4-week plan for shipping team-admin permission changes. Confirm staffing and include rollout safeguards."),
        ("plan_checkout_copy_update", "We need a concise 2-week rollout plan for a checkout copy refresh. Include implementation, QA, analytics checks, and staffing."),
        ("plan_search_filter_redesign", "We need a concise 4-week rollout plan for a search filter redesign. Pull major workstreams, launch checks, and team capacity."),
        ("plan_mobile_error_state_update", "We need a concise 3-week rollout plan for updating key mobile error states. Confirm staffing and keep the schedule realistic."),
        ("plan_settings_navigation_cleanup", "We need a concise 3-week rollout plan for a settings navigation cleanup. Pull the major tasks, confirm staffing, and note launch checks."),
    ]
    prompts.extend({"name": n, "system": planning_system, "user": u, "tools": planning_tools()} for n, u in planning_rows)

    devtool_system = (
        "You are a Rust dev-tool assistant. Use read_file, apply_patch, and the cargo tools "
        "to inspect, edit, and verify code. Inspect the source before patching so 'find' matches exactly."
    )
    # Lib bug-fix scenarios — read_file → apply_patch → cargo_test → response.
    # Paths under /srv/eval/* to avoid collisions with the SFT pool's
    # /workspace/glyph/runs/rlvr1/rust_cases/* paths.
    devtool_lib_rows = [
        ("devtool_lib_negate_sign",
         'The library at "/srv/eval/crates/lib_negate" has a test that fails because the negation function returns its input unchanged. '
         'Inspect "/srv/eval/crates/lib_negate/src/lib.rs", apply one find/replace edit, then verify with cargo_test.'),
        ("devtool_lib_min_returned_max",
         'The crate "/srv/eval/crates/lib_min" returns the slice maximum where the minimum is expected. '
         'Read "/srv/eval/crates/lib_min/src/lib.rs", patch the iterator method, and confirm cargo_test passes.'),
        ("devtool_lib_filter_predicate",
         'A failing filter in "/srv/eval/crates/lib_odd_filter" keeps even numbers instead of odd. '
         'Inspect the source under that project, flip the predicate via apply_patch, and re-run cargo_test.'),
        ("devtool_lib_fold_init",
         'The crate at "/srv/eval/crates/lib_product" reduces a slice with fold but starts from 0, so it always returns 0. '
         'Open "/srv/eval/crates/lib_product/src/lib.rs", correct the init via apply_patch, then run cargo_test.'),
        ("devtool_lib_range_off_by_one",
         'The function under "/srv/eval/crates/lib_inclusive_sum" uses an exclusive range and is off by one. '
         'Read its lib.rs, switch to an inclusive range with apply_patch, then verify via cargo_test.'),
        ("devtool_lib_string_case",
         'A helper at "/srv/eval/crates/lib_shout" returns lowercase output where the test expects uppercase. '
         'Inspect "/srv/eval/crates/lib_shout/src/lib.rs", flip the case method, and verify cargo_test.'),
        ("devtool_lib_byte_vs_char",
         'The word-counter under "/srv/eval/crates/lib_wc" returns byte length, not whitespace-delimited word count. '
         'Read the source, patch the expression with apply_patch, then re-run cargo_test.'),
        ("devtool_lib_palindrome_reverse",
         'A palindrome predicate at "/srv/eval/crates/lib_pal" forgot to reverse the chars iterator before comparing. '
         'Inspect "/srv/eval/crates/lib_pal/src/lib.rs", insert the missing .rev() via apply_patch, and verify with cargo_test.'),
    ]
    prompts.extend({"name": n, "system": devtool_system, "user": u, "tools": rust_dev_tools()} for n, u in devtool_lib_rows)

    # Bin bug-fix scenarios — read_file → apply_patch → cargo_run → response.
    devtool_bin_rows = [
        ("devtool_bin_greeting",
         'The binary at "/srv/eval/bins/greet_app" prints "goodbye" but the spec expects "hello". '
         'Inspect "/srv/eval/bins/greet_app/src/main.rs", patch the string, and verify with cargo_run.'),
        ("devtool_bin_sum_reducer",
         'The bin crate "/srv/eval/bins/sum_app" prints the product of the slice rather than the sum (expected stdout: "10"). '
         'Read its main.rs, switch the reducer via apply_patch, then run cargo_run.'),
        ("devtool_bin_squared",
         'A loop in "/srv/eval/bins/squares_app" doubles each value where it should square them (expected stdout: "1 4 9 16"). '
         'Inspect "/srv/eval/bins/squares_app/src/main.rs", patch the expression, and verify with cargo_run.'),
        ("devtool_bin_reverse_string",
         'The program at "/srv/eval/bins/rev_app" prints the unreversed string (expected stdout: "tsur"). '
         'Read main.rs, add the missing .rev() via apply_patch, and confirm cargo_run output.'),
        ("devtool_bin_range_inclusive",
         'The counter at "/srv/eval/bins/count_app" stops one short of the upper bound (expected stdout: "1 2 3 4 5"). '
         'Inspect main.rs, switch to an inclusive range, and verify cargo_run prints the full sequence.'),
    ]
    prompts.extend({"name": n, "system": devtool_system, "user": u, "tools": rust_dev_tools()} for n, u in devtool_bin_rows)

    # Single-tool exercises — cover each tool at least once without bug fixing.
    devtool_single_rows = [
        ("devtool_run_print_hello",
         'Run the Cargo binary at "/srv/eval/bins/hello_only" via cargo_run and tell me what it prints.'),
        ("devtool_run_fizzbuzz",
         'Use cargo_run on "/srv/eval/bins/fizzbuzz_short" and summarize the first three lines of stdout.'),
        ("devtool_build_release_pipeline",
         'Run cargo_build on "/srv/eval/bins/release_pipeline" and report whether it compiles cleanly.'),
        ("devtool_build_workspace_lint",
         'Run cargo_build on the Cargo project at "/srv/eval/bins/workspace_lint" and tell me if the build succeeds.'),
        ("devtool_check_optionlib",
         'Issue a cargo_check call against "/srv/eval/crates/optionlib_eval" and confirm whether it type-checks.'),
        ("devtool_check_traits_lib",
         'Run cargo_check on "/srv/eval/crates/traits_lib" and report any diagnostics it surfaces.'),
        ("devtool_test_passing_suite",
         'Use cargo_test on "/srv/eval/crates/sortlib_eval" to confirm the test suite is green.'),
        ("devtool_test_dedup_suite",
         'Run cargo_test on the crate at "/srv/eval/crates/dedup_lib" and report the outcome.'),
        ("devtool_rustc_compile_hello",
         'Compile the standalone Rust file "/srv/eval/standalone/hello_one.rs" to "/srv/eval/standalone/hello_one_bin" via rustc.'),
        ("devtool_rustc_compile_sum",
         'Use rustc to build "/srv/eval/standalone/sum_one.rs" into the binary "/srv/eval/standalone/sum_one_bin".'),
        ("devtool_read_show_lib",
         'Show me the contents of "/srv/eval/crates/showcase_lib/src/lib.rs" so I can review its public API.'),
        ("devtool_read_inspect_main",
         'Open "/srv/eval/bins/inspect_main_app/src/main.rs" and describe what the program does in one sentence.'),
    ]
    prompts.extend({"name": n, "system": devtool_system, "user": u, "tools": rust_dev_tools()} for n, u in devtool_single_rows)

    assert len(prompts) == 125, len(prompts)

    names = [row["name"] for row in prompts]
    users = [row["user"] for row in prompts]
    assert len(names) == len(set(names)), "duplicate names"
    assert len(users) == len(set(users)), "duplicate user prompts"

    dataset_text = DATASET_PATH.read_text() if DATASET_PATH.exists() else ""
    overlaps = [row["name"] for row in prompts if row["user"] in dataset_text]
    if overlaps:
        raise SystemExit(f"exact user overlap with training set: {overlaps}")

    payload = {"formal_eval": prompts}
    OUTPUT_PATH.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))
    print(f"Wrote {OUTPUT_PATH} with {len(prompts)} prompts and 0 exact overlaps.")


if __name__ == "__main__":
    main()
