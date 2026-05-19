#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.validator import validate_trace
from synthetic_data.glyph_gold50 import build_gold50 as g


OUT = Path(__file__).parent / "gold_glyph_300.jsonl"


def rustdoc_tools():
    return [g.tool("rustdoc_lookup", "Returns concise documentation for a Rust symbol.", g.param("symbol", "string", "Rust symbol"))]


def cargo_tools():
    return [
        g.tool("cargo_check", "Runs cargo check on a Rust crate and returns the main compiler diagnostics.", g.param("crate_path", "string", "Path to the crate", required=False)),
        g.tool("cargo_test", "Runs cargo test and returns failing test output.", g.param("crate_path", "string", "Path to the crate", required=False), g.param("filter", "string", "Optional test filter", required=False)),
        g.tool("cargo_clippy", "Runs cargo clippy and returns the main lints.", g.param("crate_path", "string", "Path to the crate", required=False)),
        g.tool("rustdoc_lookup", "Returns concise documentation for a Rust type, trait, macro, or function.", g.param("symbol", "string", "Rust symbol to look up", required=False)),
    ]


def ci_tools():
    return [
        g.tool("get_ci_logs", "Fetches CI logs for a run.", g.param("run_id", "string", "Run id")),
        g.tool("code_search", "Searches the codebase.", g.param("query", "string", "Search query")),
        g.tool("fetch_cached_incident", "Returns a cached incident note.", g.param("service", "string", "Service name")),
    ]


def sql_tools():
    return [g.tool("run_sql", "Executes a read-only SQL query.", g.param("query", "string", "SQL query text"))]


def math_tools():
    return [
        g.tool("solve_symbolic", "Performs symbolic math operations.", g.param("expression", "string", "Expression"), g.enum_param("operation", ("integrate", "differentiate", "simplify", "factor"), "Operation"), g.param("variable", "string", "Variable")),
        g.tool("derivative_check", "Differentiates a candidate and compares it to a target expression.", g.param("candidate_antiderivative", "string", "Candidate"), g.param("target_expression", "string", "Target"), g.param("variable", "string", "Variable")),
    ]


def file_tools():
    return [g.tool("load_file", "Loads a file from disk and returns a short excerpt.", g.param("path", "string", "Path to load"))]


def plan_tools():
    return [
        g.tool("get_availability", "Returns weekly availability by teammate.", g.param("team_list", "string", "Comma-separated IDs", required=False), g.param("start_date", "string", "Start date", required=False), g.param("end_date", "string", "End date", required=False)),
        g.tool("create_project_plan", "Generates a short work breakdown.", g.param("project_name", "string", "Project name", required=False), g.param("objectives", "string", "Objectives", required=False), g.param("timeline_weeks", "string", "Timeline in weeks", required=False)),
    ]


def git_tools():
    return [
        g.tool("git_status", "Returns a concise git status (branch, dirty files, and staged changes).", g.param("repo_path", "string", "Path to the git repository", required=False)),
        g.tool("git_log", "Shows recent commits in a concise one-line format.", g.param("repo_path", "string", "Path to the git repository", required=False), g.param("limit", "number", "Maximum number of commits to show", required=False)),
    ]


def extend_records() -> list[str]:
    traces = g.records()
    rd = rustdoc_tools()
    cargo = cargo_tools()
    ci = ci_tools()
    sql = sql_tools()
    math = math_tools()
    files = file_tools()
    plans = plan_tools()
    git = git_tools()

    rust_no_tool = [
        (
            "You are a Rust language assistant who gives compact conceptual explanations.",
            "Why would you choose `Cow<'a, str>` over always returning `String` from a text-normalization API?",
            "Explain the main allocation tradeoff and when Cow is useful.",
            "State the borrow-vs-own tradeoff briefly.",
            "Keep it centered on avoiding needless allocation when most outputs can stay borrowed.",
            "Cow is useful when most results can stay borrowed but some cases need owned output. It lets the API avoid allocating a fresh String unless normalization actually changes the text.",
            "note_cow_api",
        ),
        (
            "You are a Rust API design assistant who answers briefly.",
            "Why is `Result<T, E>` usually better than panicking in library code?",
            "Explain why library code should prefer Result over panic.",
            "Tie the answer to caller control and recoverability.",
            "Emphasize that libraries should return failures to callers rather than deciding to abort the flow themselves.",
            "Result is usually better because it lets the caller decide whether to retry, recover, transform, or surface the error. A panic is appropriate only for broken invariants or impossible states, not normal operational failure.",
            "note_result_vs_panic",
        ),
        (
            "You are a Rust trait-system explainer who writes concise answers.",
            "Why do people use `impl Trait` in return position instead of exposing a concrete iterator type?",
            "Explain the main API design advantage of impl Trait in return position.",
            "Connect it to abstraction and refactor freedom.",
            "Keep it focused on hiding noisy concrete types while preserving static dispatch.",
            "`impl Trait` in return position hides the concrete type while keeping static dispatch, which makes public APIs easier to read and easier to change internally later. It is especially useful for iterators and closures whose concrete types are verbose and unstable implementation details.",
            "note_impl_trait_return",
        ),
        (
            "You are a Rust async explainer who writes concise technical answers.",
            "Why is `spawn_blocking` different from `tokio::spawn`?",
            "Explain when spawn_blocking is the right choice.",
            "Tie the answer to executor threads versus blocking work.",
            "State that spawn_blocking is for CPU-heavy or blocking operations that should not stall async worker threads.",
            "`spawn_blocking` runs work on a dedicated blocking pool so slow CPU-bound or blocking code does not stall Tokio’s async worker threads. `tokio::spawn` is for ordinary async tasks that should yield rather than block.",
            "note_spawn_blocking",
        ),
        (
            "You are a concise Rust concurrency mentor.",
            "Why might `Arc<RwLock<T>>` be a better fit than `Arc<Mutex<T>>` for some workloads?",
            "Explain the read-heavy tradeoff briefly.",
            "Connect it to shared reads versus exclusive writes.",
            "Keep it focused on allowing concurrent readers when writes are rare.",
            "`Arc<RwLock<T>>` can be a better fit when reads dominate and writes are rare, because multiple readers can proceed at once while writes still stay exclusive. `Arc<Mutex<T>>` is simpler but forces all access through one exclusive lock.",
            "note_rwlock",
        ),
        (
            "You are a Rust ownership assistant who gives compact explanations.",
            "Why is `into_iter()` different on `Vec<T>` versus `&Vec<T>`?",
            "Explain the ownership difference briefly.",
            "Tie the answer to moved items versus borrowed items.",
            "State that the receiver type determines whether iteration yields owned values or references.",
            "`into_iter()` depends on the receiver type: on `Vec<T>` it consumes the vector and yields owned `T` values, while on `&Vec<T>` it iterates borrowed references. The difference comes from whether the collection itself is moved or only borrowed.",
            "note_into_iter",
        ),
        (
            "You are a practical Rust performance explainer.",
            "Why would you choose `Vec::with_capacity` before pushing many items in a loop?",
            "Explain the allocation benefit briefly.",
            "Connect it to reducing reallocations.",
            "Keep it focused on reserving space up front when approximate size is known.",
            "Using `Vec::with_capacity` reserves space up front so repeated pushes are less likely to trigger reallocations and copies. It is most useful when you have a reasonable estimate of the final size.",
            "note_capacity_perf",
        ),
        (
            "You are a concise Rust error-handling mentor.",
            "Why is a custom error enum often better than returning boxed dynamic errors everywhere?",
            "Explain the tradeoff between explicit enums and boxed errors.",
            "Tie the answer to exhaustiveness and API clarity.",
            "Keep it focused on making failure modes visible and pattern-matchable.",
            "A custom error enum makes the failure surface explicit and easy to pattern match, which improves API clarity and caller control. Boxed dynamic errors are more flexible but hide which concrete failures are expected.",
            "note_error_enum",
        ),
        (
            "You are a Rust testing assistant who answers briefly.",
            "Why do deterministic tests avoid reading the current time directly?",
            "Explain the test-stability reason briefly.",
            "Tie it to repeatability and hidden time dependencies.",
            "Keep it focused on making tests reproducible by injecting clocks or fixed timestamps.",
            "Tests avoid reading the real current time directly because wall-clock dependence makes behavior vary across runs and environments. Injecting a clock or fixed timestamp makes the test repeatable and easier to reason about.",
            "note_time_tests",
        ),
        (
            "You are a Rust lifetime explainer who writes concise answers.",
            "Why is `&str` often fine for function parameters but awkward for stored struct fields?",
            "Explain the lifetime difference briefly.",
            "Connect it to temporary borrows versus long-lived ownership.",
            "Keep it focused on the fact that stored borrows force lifetime parameters through the whole type.",
            "`&str` is often great for function parameters because the borrow only needs to live for the call. As a stored struct field it becomes much more awkward, because the whole struct must then carry and satisfy that lifetime.",
            "note_str_param_vs_field",
        ),
        (
            "You are a concise Rust collections explainer.",
            "Why might you choose `VecDeque` instead of `Vec` for a queue?",
            "Explain the queue-specific tradeoff briefly.",
            "Tie it to front insertion and removal costs.",
            "Keep it focused on avoiding repeated shifting at the front.",
            "`VecDeque` is better for queue-like workloads because pushing or popping at the front is efficient, while a plain Vec has to shift elements for front removals or insertions. If you only push/pop at the back, Vec is usually simpler.",
            "note_vecdeque",
        ),
        (
            "You are a Rust systems explainer who writes concise answers.",
            "Why can `Path` / `PathBuf` be safer than assuming UTF-8 strings for filesystem paths?",
            "Explain the portability reason briefly.",
            "Tie it to platform-native path representations.",
            "Keep it focused on paths not always being valid UTF-8 and on path-specific operations.",
            "Path and PathBuf are safer because filesystem paths are platform-native values, not guaranteed UTF-8 text. They also provide path-aware operations like joining and extension handling without forcing lossy string conversion.",
            "note_path_utf8",
        ),
        (
            "You are a Rust trait-bound assistant who answers briefly.",
            "Why would a generic function take `AsRef<Path>` instead of `&Path` directly?",
            "Explain the API ergonomics briefly.",
            "Tie it to accepting more input types without allocating.",
            "Keep it focused on flexible caller inputs like String, PathBuf, and &Path.",
            "Taking `AsRef<Path>` lets the function accept several path-like inputs such as `&Path`, `PathBuf`, `String`, or `&str` without forcing callers to convert first. It keeps the API flexible while still working with borrowed paths internally.",
            "note_asref_path",
        ),
        (
            "You are a Rust borrowing explainer who writes concise answers.",
            "Why does collecting references into a Vec sometimes fail when the source data is temporary?",
            "Explain the lifetime issue briefly.",
            "Tie it to borrowed elements outliving the collection they came from.",
            "Keep it focused on references needing backing storage that survives long enough.",
            "Collecting references fails when those references point into temporary data that is dropped too soon. The collected Vec of references can only live as long as the backing data it borrows from.",
            "note_collect_refs",
        ),
        (
            "You are a concise Rust async mentor.",
            "Why is it risky to hold a mutex guard across `.await` points?",
            "Explain the async locking issue briefly.",
            "Tie it to deadlocks and reduced concurrency.",
            "Keep it focused on a suspended future holding shared state hostage.",
            "Holding a mutex guard across `.await` is risky because the future can suspend while still holding the lock, blocking other tasks from making progress and sometimes creating deadlock patterns. The usual fix is to keep the critical section small and release the guard before awaiting.",
            "note_guard_await",
        ),
        (
            "You are a Rust API ergonomics assistant who answers briefly.",
            "Why is `&[T]` often a better function parameter than `&Vec<T>`?",
            "Explain the slice-based API benefit briefly.",
            "Tie it to accepting more caller types.",
            "Keep it focused on slices being the more general borrowed view.",
            "`&[T]` is usually better because it accepts borrowed arrays, Vecs, and other contiguous slices without requiring a specific container type. It makes the API more general while still giving read-only indexed access to the elements.",
            "note_slice_param",
        ),
        (
            "You are a concise Rust memory-model explainer.",
            "Why might `Arc<[T]>` be preferable to `Arc<Vec<T>>` after a collection is finalized?",
            "Explain the representation benefit briefly.",
            "Tie it to immutability and avoiding spare capacity.",
            "Keep it focused on frozen shared data.",
            "`Arc<[T]>` can be preferable once the data is finalized because it represents an immutable slice without Vec-specific spare capacity or mutability semantics. It is a tighter fit for shared read-only collections.",
            "note_arc_slice",
        ),
        (
            "You are a Rust ownership mentor who answers briefly.",
            "Why is cloning inside a hot loop often a code smell in Rust?",
            "Explain the performance and ownership hint briefly.",
            "Tie it to hidden allocation or copying costs.",
            "Keep it focused on cloning as a signal that ownership boundaries may be off.",
            "Cloning inside a hot loop is often a smell because it can hide repeated allocation or copying costs, especially if it exists only to satisfy ownership. It often means the code should borrow differently, restructure data flow, or clone once outside the loop instead.",
            "note_clone_loop",
        ),
        (
            "You are a concise Rust trait-object explainer.",
            "Why might `Box<dyn Error>` be acceptable at an application boundary even if a library should prefer explicit error enums?",
            "Explain the boundary tradeoff briefly.",
            "Tie it to application glue versus reusable API design.",
            "Keep it focused on top-level aggregation and reduced boilerplate at the app boundary.",
            "At an application boundary, `Box<dyn Error>` can be acceptable because the program often just needs to surface or log failures rather than expose structured error handling to callers. Libraries usually prefer explicit enums because they are reusable APIs and should document their failure modes clearly.",
            "note_box_dyn_error_boundary",
        ),
        (
            "You are a concise Rust compiler mentor.",
            "Why does the compiler sometimes ask for a type annotation on `collect()` even when the iterator item type is obvious?",
            "Explain the missing information briefly.",
            "Tie it to the destination collection type being ambiguous.",
            "Keep it focused on collect knowing the item type but not the final container.",
            "Even when the iterator item type is obvious, `collect()` still needs to know which destination type to build. The missing information is usually the output collection type, not the iterator element type.",
            "note_collect_annotation",
        ),
        (
            "You are a practical Rust CLI assistant who answers briefly.",
            "Why is `PathBuf` usually a better clap field type than `String` for file arguments?",
            "Explain the clap/path reason briefly.",
            "Tie it to semantic correctness and fewer conversions.",
            "Keep it focused on parsing user input directly into path-aware types.",
            "Using `PathBuf` for clap file arguments is usually better because the value semantically is a path, and clap can parse directly into that type. It avoids extra conversions and preserves platform path behavior more faithfully than plain String.",
            "note_clap_pathbuf",
        ),
    ]
    for item in rust_no_tool:
        traces.append(g.no_tool_trace(*item))

    rust_doc_items = [
        ("std::mem::replace", "Replaces the value at a mutable location and returns the old value.", "std::mem::replace lets you swap in a new value and take the old one out in a single move-safe operation."),
        ("std::mem::swap", "Swaps the values at two mutable locations.", "std::mem::swap exchanges two values in place without cloning or allocating."),
        ("Option::as_ref", "Converts from `&Option<T>` to `Option<&T>`.", "Option::as_ref lets you borrow the contents of an Option without taking ownership."),
        ("Option::as_mut", "Converts from `&mut Option<T>` to `Option<&mut T>`.", "Option::as_mut gives mutable borrowed access to the contents of an Option without moving them out."),
        ("Result::map_err", "Transforms the error variant of a Result while leaving the success value unchanged.", "Result::map_err is used when the success value is fine but the error type needs conversion or cleanup."),
        ("Result::transpose", "Transposes an `Option<Result<T,E>>` into a `Result<Option<T>,E>`.", "Result::transpose flips nested Option/Result structure so error handling can happen at the outer Result layer."),
        ("Iterator::collect", "Transforms an iterator into a collection or other type implementing FromIterator.", "Iterator::collect consumes an iterator and builds a destination type such as Vec, String, or HashMap."),
        ("Iterator::try_fold", "Like fold, but stops early if the closure returns a failure-like residual.", "Iterator::try_fold combines accumulation with short-circuiting error or control-flow propagation."),
        ("Iterator::find_map", "Applies a function and returns the first non-None result.", "Iterator::find_map is useful when searching and transforming in one pass."),
        ("Iterator::enumerate", "Yields `(index, item)` pairs from an iterator.", "Iterator::enumerate adds a running index to each item as you iterate."),
        ("Iterator::zip", "Pairs items from two iterators into tuples until either iterator ends.", "Iterator::zip is useful when processing two sequences in lockstep."),
        ("Iterator::flatten", "Removes one level of nesting from an iterator of iterables.", "Iterator::flatten turns nested iteration like `Vec<Vec<T>>` or `Iterator<Item = Option<T>>` into a flatter stream."),
        ("Vec::drain", "Removes a range from a vector and yields the removed items as an iterator.", "Vec::drain is useful when you want to move items out of part of a Vec while mutating the Vec in place."),
        ("Vec::retain", "Retains only the elements specified by a predicate.", "Vec::retain filters a vector in place without allocating a new one."),
        ("Vec::splice", "Replaces a range in a vector with items from another iterator and yields the removed items.", "Vec::splice is an in-place replace-and-yield operation for a slice of a Vec."),
        ("String::from_utf8", "Attempts to build a String from bytes, returning an error if the bytes are not valid UTF-8.", "String::from_utf8 is the checked conversion from raw bytes into a UTF-8 String."),
        ("str::split_once", "Splits a string on the first occurrence of a pattern and returns the two parts.", "split_once is useful when you only need one delimiter split instead of all segments."),
        ("str::strip_prefix", "Returns the string without a prefix if the prefix is present.", "strip_prefix is a clean way to parse known prefixes without manual slicing."),
        ("str::lines", "Returns an iterator over the lines of a string slice.", "str::lines is the standard line iterator for borrowed text data."),
        ("Path::join", "Creates a new owned path by appending a child path to a base path.", "Path::join is the standard way to append path components without manual separator handling."),
        ("Path::parent", "Returns the parent path, if there is one.", "Path::parent is useful when you need to navigate up one directory level safely."),
        ("Path::extension", "Returns the extension of a path, if present.", "Path::extension gives a path-aware way to inspect filename suffixes."),
        ("PathBuf::push", "Appends a path component onto a PathBuf in place.", "PathBuf::push mutates a PathBuf by adding another component using platform path rules."),
        ("HashMap::get", "Returns a reference to the value for a key, if it exists.", "HashMap::get is the basic borrowed lookup API for optional keyed access."),
        ("HashMap::insert", "Inserts a key-value pair into the map, returning the old value if the key already existed.", "HashMap::insert is the normal write/update API for keyed values."),
        ("HashMap::remove", "Removes a key from the map, returning its value if present.", "HashMap::remove deletes a key and gives ownership of the removed value back to the caller."),
        ("HashSet::contains", "Checks whether a set contains a value.", "HashSet::contains is the basic membership test for set-like lookups."),
        ("BTreeSet::range", "Visits elements in a sorted set within a given range.", "BTreeSet::range is useful when ordered queries matter, not just membership."),
        ("Box::leak", "Consumes a Box and returns a mutable reference with a `'static` lifetime.", "Box::leak intentionally gives up deallocation so the boxed value can live for the remainder of the program."),
        ("Arc::clone", "Creates another shared-owner handle to the same allocation by incrementing the atomic refcount.", "Arc::clone is cheap shared-owner duplication; it clones the pointer, not the inner value."),
        ("Rc::clone", "Creates another shared-owner handle in a single-threaded context by incrementing the non-atomic refcount.", "Rc::clone is cheap pointer-level cloning for single-threaded shared ownership."),
        ("RefCell::borrow_mut", "Mutably borrows the wrapped value at runtime, panicking if the borrow rules are violated.", "RefCell::borrow_mut enables interior mutability with runtime borrow checking."),
        ("std::cell::Cell", "Provides simple interior mutability for Copy-like set/get use cases without returning references.", "Cell is useful for small copyable values that need mutation through shared references."),
        ("Pin::new", "Pins a pointer type so the pointee is treated as immovable for APIs that require pinning.", "Pin::new wraps a pointer in Pin when the pointee's location must stay stable."),
        ("Pin::as_mut", "Reborrows a pinned mutable reference so pinned methods can be called without moving the value.", "Pin::as_mut is a helper for working with pinned values through nested APIs."),
        ("tokio::spawn", "Spawns an asynchronous task onto the Tokio runtime.", "tokio::spawn runs a future concurrently on the runtime and typically requires the future to be Send on the multithreaded runtime."),
        ("tokio::task::spawn_blocking", "Runs blocking work on a dedicated blocking thread pool.", "spawn_blocking is the right escape hatch for synchronous or CPU-heavy code that should not block async workers."),
        ("tokio::sync::mpsc::channel", "Creates a multi-producer, single-consumer async channel.", "tokio::sync::mpsc::channel is a common async message-passing primitive between tasks."),
        ("tokio::time::timeout", "Wraps a future and returns an error if it does not complete before a duration elapses.", "tokio::time::timeout is used to put an upper bound on how long an async operation may take."),
        ("serde_json::from_str", "Parses JSON text into a Rust value implementing Deserialize.", "serde_json::from_str is the standard entry point for turning JSON text into typed Rust data."),
        ("serde_json::to_string", "Serializes a Rust value implementing Serialize into a JSON string.", "serde_json::to_string converts typed Rust data into owned JSON text."),
        ("std::fs::read_to_string", "Reads an entire file into a String.", "read_to_string is a convenient whole-file helper when UTF-8 text fits in memory."),
        ("std::fs::metadata", "Queries filesystem metadata such as size, permissions, and file type.", "metadata is the standard way to inspect file information before acting on it."),
        ("std::io::BufRead::lines", "Returns an iterator over the lines of a buffered reader.", "BufRead::lines is useful for incremental text file processing without loading the whole file first."),
        ("std::process::Command", "Builds and runs child processes with configurable arguments and environment.", "Command is the standard Rust API for spawning external programs."),
        ("std::thread::spawn", "Starts a new OS thread running a closure.", "thread::spawn moves work onto a new thread and usually requires moved data to be Send."),
        ("std::sync::mpsc::channel", "Creates a standard library multi-producer, single-consumer channel.", "std::sync::mpsc::channel is the basic message-passing primitive for thread-based concurrency in std."),
        ("f32::total_cmp", "Provides a total ordering for floating-point values, including NaN.", "f32::total_cmp is the right comparator when floats must be sorted deterministically."),
        ("std::cmp::Reverse", "Wraps a value so ordering comparisons are reversed.", "Reverse is often used to turn min-heaps into max-heaps or sort descending with existing Ord implementations."),
        ("BinaryHeap", "A priority queue implemented as a binary heap.", "BinaryHeap is useful when you repeatedly need the largest or smallest item by priority rather than full sorting."),
        ("Vec::sort_by_key", "Sorts a vector using a key extraction function.", "sort_by_key is convenient when ordering depends on a derived key rather than the full element."),
        ("slice::windows", "Returns overlapping fixed-size windows over a slice.", "windows is useful for pairwise or rolling computations over borrowed contiguous data."),
        ("slice::chunks", "Returns non-overlapping chunks of a slice.", "chunks is useful for batch-style processing of slice data."),
        ("Iterator::peekable", "Wraps an iterator so the next item can be inspected without consuming it.", "peekable is helpful in parsers and token streams where lookahead is needed."),
        ("Option::ok_or_else", "Converts an Option into a Result, lazily generating the error only if needed.", "ok_or_else is useful when missing optional data should become a computed error."),
        ("Result::and_then", "Chains another fallible computation onto a successful Result.", "and_then is the monadic chaining combinator for fallible sequential work."),
        ("Result::unwrap_or_else", "Extracts the success value or computes a fallback from the error.", "unwrap_or_else is useful when failure should map to a computed default rather than immediate propagation."),
    ]
    for symbol, result_data, response in rust_doc_items:
        user = f"In Rust, what does {symbol} do? Use the docs tool."
        if symbol in {"HashMap::entry", "BTreeSet::range", "BinaryHeap", "f32::total_cmp"}:
            user = {
                "HashMap::entry": "What does `HashMap::entry` help with in Rust? Use the docs tool.",
                "BTreeSet::range": "When is `BTreeSet::range` useful in Rust? Use the docs tool.",
                "BinaryHeap": "What is `BinaryHeap` useful for in Rust? Use the docs tool.",
                "f32::total_cmp": "Why would you use `f32::total_cmp` in Rust? Use the docs tool.",
            }[symbol]
        traces.append(
            g.single_tool_trace(
                "You are a Rust documentation assistant who answers briefly and precisely.",
                rd,
                user,
                [f"Look up {symbol} in the docs tool.", "Explain it briefly."],
                "Use one tool call, then summarize the behavior briefly.",
                "rustdoc_lookup",
                [("symbol", symbol)],
                "res1",
                result_data,
                "Use the returned definition directly and keep the final explanation short.",
                "note1",
                response,
            )
        )

    rust_debug_items = [
        (
            "My Rust crate fails to compile after I changed a function to use `?` on a `std::fmt::Result` inside one helper but return `io::Result<()>` from the outer function. What is the likely fix?",
            "cargo check: error[E0277]: `?` couldn't convert the error to `std::io::Error`; the trait `From<std::fmt::Error>` is not implemented for `std::io::Error`.",
            "FromResidual",
            "The compiler is pointing at a missing conversion path between two unrelated error types.",
            "The `?` operator is trying to turn `std::fmt::Error` into `std::io::Error`, but no such conversion exists. Fix it by normalizing the return error type, mapping the formatting error explicitly with `map_err`, or avoiding a mixed error boundary in that helper.",
            "cargo_check",
        ),
        (
            "My Rust function returns `iter.filter(...)` from a local Vec and now the compiler says the returned value references local data. What did I do wrong?",
            "cargo check: error[E0515]: cannot return value referencing local variable `items`; the returned iterator borrows `items`.",
            "impl Trait return lifetime iterator",
            "The returned iterator is borrowing from a local collection that will be dropped before the caller can use it.",
            "You returned a borrowing iterator over a local Vec, so the iterator outlives the data it references. Return an owning iterator (for example with `into_iter()`), return the owned collection instead, or borrow from caller-owned data rather than a local temporary.",
            "cargo_check",
        ),
        (
            "My Rust code uses `for x in items.iter()` and then `items.push(...)` inside the loop. What is the compiler objecting to?",
            "cargo check: error[E0502]: cannot borrow `items` as mutable because it is also borrowed as immutable by the iterator.",
            "Iterator::iter",
            "The compiler output already shows the classic mutate-while-iterating pattern.",
            "The loop holds an immutable borrow through `items.iter()`, so pushing into the same Vec would require a conflicting mutable borrow. The usual fix is to collect additions separately, iterate over a snapshot, or restructure the loop so mutation happens after iteration.",
            "cargo_check",
        ),
        (
            "My async Rust tests hang and I suspect a deadlock around a mutex. What should I check first?",
            "cargo test output: test hangs after log line `acquired state lock`; no later log lines appear.",
            "tokio::sync::Mutex",
            "The symptom strongly suggests a task is holding a lock while waiting for something that also needs the lock.",
            "First check whether a mutex guard is held across an `.await`, because that is a common async deadlock pattern. Then inspect lock ordering and any blocking calls inside the critical section; adding logs around acquisition and release usually narrows it down quickly.",
            "cargo_test",
        ),
        (
            "My Rust helper stores different iterator adapters in one Vec and now I get mismatched-type errors. What is the clean fix?",
            "cargo check: error[E0308]: expected `Map<_, _>`, found `Filter<_, _>`; each iterator adapter has a distinct concrete type.",
            "dyn Iterator",
            "This is a heterogeneous-iterator storage problem rather than a generic inference issue.",
            "Different iterator adapters have different concrete types even when they share the `Iterator` trait. A clean fix is to store `Box<dyn Iterator<Item = T>>`, use an enum wrapper if the set is closed, or collect to concrete data before storing.",
            "cargo_check",
        ),
        (
            "My Rust test sorts floats with `partial_cmp(...).unwrap()` and now it fails on NaN. What should I do instead?",
            "cargo test panic: comparator uses `a.partial_cmp(b).unwrap()` and hit a NaN case.",
            "f32::total_cmp",
            "The failure comes from assuming floats always have a comparable ordering under partial_cmp.",
            "Use `f32::total_cmp` when floats need deterministic sorting, because `partial_cmp` returns None for NaN. If the test also needs stable ordering for equal keys, use a stable sort or add an explicit tie-breaker key.",
            "cargo_test",
        ),
        (
            "My Rust code stores a closure that captures `&local` in a struct field and now the compiler says `local` does not live long enough. Why?",
            "cargo check: error[E0597]: `local` does not live long enough; closure may outlive the current function, but it borrows `local`.",
            "FnOnce + 'static",
            "The closure is escaping the scope of borrowed data that will be dropped too soon.",
            "The closure is trying to outlive a borrowed local reference, so the compiler rejects it. Fix it by moving owned data into the closure, parameterizing the struct with an explicit lifetime if that really matches the API, or redesigning the closure so it does not escape the local scope.",
            "cargo_check",
        ),
        (
            "My Rust function returns `&s` where `s` is a local String. Why is that invalid?",
            "cargo check: error[E0515]: cannot return reference to local variable `s`.",
            "lifetime elision",
            "The returned reference would outlive the local String that owns the data.",
            "A reference to a local String becomes dangling as soon as the function returns, so the compiler forbids it. Return an owned String instead, or return a borrow tied to data owned by the caller rather than data created inside the function.",
            "cargo_check",
        ),
        (
            "Clippy says an unknown lint name is configured in CI, but I cannot run clippy here. What is the most likely issue?",
            "cargo clippy unavailable; CI error mentions unknown lint `clippy::foo_bar_baz`.",
            "unknown_lints",
            "Unknown lint names are usually version skew or renamed/removed lints rather than mysterious codegen failures.",
            "The most likely issue is a toolchain mismatch or a lint that was renamed or removed in the CI Clippy version. Check the exact Rust/Clippy version in CI, update or remove the stale lint name, and use `allow(unknown_lints)` only as a temporary unblock while versions are aligned.",
            "cargo_clippy",
        ),
        (
            "My clap-based config struct started failing after I changed a field from `Vec<String>` to `Vec<&str>`. What is the likely issue?",
            "cargo check: error[E0106]: missing lifetime specifier; error[E0521]: borrowed data escapes outside of function from clap parsing.",
            "clap derive String vs &str",
            "This is the classic borrowed-config-field problem rather than anything clap-specific about parsing syntax.",
            "The likely issue is that the config struct is trying to store borrowed strings that do not outlive the parse context. Prefer owned `String` values for clap-derived config structs unless you have a very deliberate lifetime-carrying design.",
            "cargo_check",
        ),
        (
            "My unit test started panicking with `called Option::unwrap() on a None value` after a dependency update. What should I check first?",
            "cargo test: thread `tests::parses_config` panicked at `called Option::unwrap() on a None value`, src/config.rs:87:22",
            "Option::unwrap",
            "The update probably changed an assumption about presence rather than causing a random runtime failure.",
            "Start by checking what value became None at that unwrap site and why the dependency update changed that assumption. Replace the blind unwrap with logging, pattern matching, or `expect(...)` carrying context so you can confirm whether parsing behavior, defaults, or input shape changed.",
            "cargo_test",
        ),
        (
            "My workspace builds, but one unit test now fails with an assertion after a serde_json upgrade. What is a likely cause?",
            "cargo test failure: expected field order in JSON string differs after upgrade; semantic values still match.",
            "serde_json::to_string",
            "The symptom points to a test assuming a particular serialization layout rather than a broken semantic parse.",
            "A likely cause is that the test assumed a specific serialized string form, including field order or formatting, rather than comparing semantic JSON values. Prefer parsing back into `serde_json::Value` or comparing structured data instead of exact serialized string layout.",
            "cargo_test",
        ),
        (
            "My Rust async service uses `std::sync::Mutex` inside async handlers and throughput collapsed. What should I suspect first?",
            "cargo check succeeds, but profiling shows long waits around a shared `std::sync::Mutex` in request handlers.",
            "tokio::sync::Mutex",
            "The service is likely blocking executor threads around a synchronous mutex in async code.",
            "First suspect that a synchronous mutex is blocking async worker threads under load. If the protected work truly belongs in async request handlers, switch to `tokio::sync::Mutex` or restructure ownership so the critical section stays tiny and does not block the runtime.",
            "cargo_check",
        ),
        (
            "My Rust code uses `.collect()` into a HashMap and the compiler asks for type annotations. What exactly is missing?",
            "cargo check: error[E0283]: type annotations needed; cannot infer type parameter `B` on method `collect`; consider `collect::<std::collections::HashMap<_, _>>()`.",
            "Iterator::collect",
            "The compiler knows the item type but not which final collection type it should construct.",
            "What is missing is the destination collection type, not the iterator element type. Add a variable type annotation or a turbofish like `collect::<HashMap<_, _>>()` so the compiler knows which FromIterator implementation to use.",
            "cargo_check",
        ),
        (
            "My Rust code moved a String out of `*item` while iterating borrowed elements and now I get E0507. What is the likely fix?",
            "cargo check: error[E0507]: cannot move out of `*item` which is behind a shared reference; consider borrowing instead of moving.",
            "Iterator::iter",
            "The code is trying to move ownership out through a shared borrow.",
            "You are iterating borrowed elements but then trying to move the owned String out of them. The fix is usually to keep borrowing (`&str` / `&String`), clone only if truly needed, or iterate over owned values instead of shared references if consumption is intended.",
            "cargo_check",
        ),
        (
            "My Rust parser uses `split_once` and now I get `None` on some inputs after a format change. How should I think about the fix?",
            "cargo test output: expected delimiter `:` missing on some newer inputs; `split_once(':')` returned None.",
            "str::split_once",
            "The parser is assuming a delimiter that no longer exists on every line.",
            "The fix is to treat the delimiter as optional or versioned input shape rather than blindly assuming it exists. Handle the `None` case explicitly, update the expected format, or switch to a more robust parser if the input grammar changed materially.",
            "cargo_test",
        ),
        (
            "My code compiles, but clippy complains about needless allocation after `to_string()` on a path. What is the likely issue?",
            "cargo clippy warning: unnecessary allocation from `path.to_string()` before immediate borrowing.",
            "Path::display",
            "The code is allocating owned text where borrowed or display-based formatting would be enough.",
            "The likely issue is converting a path to an owned String even though the code only needs borrowed display or temporary formatting. Prefer `path.display()` for formatting or borrow the path directly when possible instead of allocating with `to_string()`.",
            "cargo_clippy",
        ),
        (
            "My `tokio::spawn` call fails because the future is not Send. What is the likely root cause?",
            "cargo check: future cannot be sent between threads safely; captured value `Rc<...>` is not Send.",
            "Send",
            "A non-Send captured value is preventing the spawned future from moving to the multithreaded runtime.",
            "The likely root cause is that the spawned future captures something like `Rc`, `RefCell`, or another non-Send type. Replace it with thread-safe equivalents like `Arc`/`Mutex`, keep the task on a local executor, or refactor what the future captures.",
            "cargo_check",
        ),
        (
            "My Rust build fails after I added a trait object field and now the compiler asks for lifetimes on it. Why?",
            "cargo check: trait object field `Box<dyn Fn(&str)>` defaults to `'static`, but captured borrow does not live long enough.",
            "dyn Trait + 'static",
            "Trait objects often default to `'static` in stored positions unless a shorter lifetime is threaded through explicitly.",
            "The compiler is warning that the stored trait object is treated as needing `'static` unless you explicitly parameterize it with a shorter lifetime. Either move owned data into the closure/object, or add the right lifetime parameter to the struct so the borrow relationship is explicit.",
            "cargo_check",
        ),
        (
            "My iterator chain compiles until I add `peekable()` and then borrow errors show up. Why can that happen?",
            "cargo check: borrowed value does not live long enough after introducing `peekable()` with references into temporary data.",
            "Iterator::peekable",
            "Peekable can extend how long a reference is held because it caches the next item for lookahead.",
            "Adding `peekable()` can change borrow timing because the adapter may hold onto the next item longer for lookahead. If those items borrow temporary data, the longer-lived cached borrow can trigger errors that were not visible in the simpler chain.",
            "cargo_check",
        ),
        (
            "My test around `BinaryHeap` expects ascending order and now fails. What is the conceptual mistake?",
            "cargo test failure: expected smallest element first, but `BinaryHeap::pop()` returned the largest.",
            "BinaryHeap",
            "The test is assuming min-heap behavior from a max-heap API.",
            "The conceptual mistake is expecting `BinaryHeap` to behave like a min-heap by default. In Rust it is a max-heap, so `pop()` returns the largest item unless you wrap keys in `Reverse` or implement an inverted ordering.",
            "cargo_test",
        ),
        (
            "I used `RefCell::borrow_mut()` twice through different code paths and now the program panics at runtime. Why didn’t the compiler stop me?",
            "runtime panic: already borrowed: BorrowMutError",
            "RefCell::borrow_mut",
            "RefCell enforces borrowing rules at runtime instead of compile time.",
            "The compiler did not stop you because `RefCell` intentionally moves borrow checking to runtime. It allows interior mutability through shared references, but if two mutable borrows overlap, the violation shows up as a runtime panic instead of a compile-time error.",
            "cargo_check",
        ),
        (
            "My code switched from `Vec<T>` to `Arc<[T]>` and now mutation no longer works. Why?",
            "cargo check: cannot borrow data in an `Arc<[T]>` as mutable; trait `DerefMut` is not implemented.",
            "Arc<[T]>",
            "The new type represents frozen shared slice data rather than an owned growable mutable vector.",
            "Arc<[T]>` is a shared immutable slice, so it is great for frozen read-only data but not for in-place mutation. If you still need mutation, keep a mutable owning structure like `Vec<T>` until the data is finalized or wrap shared mutable state explicitly.",
            "cargo_check",
        ),
    ]
    for user, primary, doc_symbol, think, response, first_tool in rust_debug_items:
        first_args = [("crate_path", "./")]
        if first_tool == "cargo_test":
            first_args = [("crate_path", "./")]
        if "sort" in user and first_tool == "cargo_test":
            first_args.append(("filter", "sort_floats"))
        traces.append(
            g.multi_tool_trace(
                "You are a Rust debugging assistant who diagnoses compiler and tool output concisely.",
                cargo,
                user,
                [
                    "Get the primary diagnostic or tool output for the failure.",
                    "Use one targeted docs lookup if it sharpens the fix.",
                    "Give a concise diagnosis and repair direction.",
                ],
                "Use one concrete tool result, optionally one supporting lookup, then answer without extra loops.",
                first_tool,
                first_args,
                "step1",
                primary,
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

    nonrust_single = [
        (
            "You are a data access assistant who uses SQL and answers briefly.",
            sql,
            "How many failed checkout attempts happened yesterday?",
            ["Query the failed checkout count.", "Answer with the count briefly."],
            "Use one SQL query, then state the returned count.",
            "run_sql",
            [("query", "SELECT COUNT(*) AS failed_checkouts_yesterday FROM checkout_events WHERE status = 'failed' AND created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE;")],
            "res1",
            "Query result: failed_checkouts_yesterday = 317.",
            "The SQL result already contains the exact number needed for the answer.",
            "note1",
            "There were 317 failed checkout attempts yesterday.",
        ),
        (
            "You are a data access assistant who uses SQL and answers briefly.",
            sql,
            "What was total revenue from completed orders in Q1 2025?",
            ["Query the completed-order revenue total.", "Report the total briefly."],
            "Use one SQL query, then answer with the total revenue figure.",
            "run_sql",
            [("query", "SELECT COALESCE(SUM(total_amount), 0) AS total_revenue FROM orders WHERE status = 'completed' AND completed_at >= DATE '2025-01-01' AND completed_at < DATE '2025-04-01';")],
            "res1",
            "Query result: total_revenue = 2487930.12",
            "The result is already a single figure, so just report it cleanly.",
            "note1",
            "Total revenue from completed orders in Q1 2025 was $2,487,930.12.",
        ),
        (
            "You are a calculation assistant who returns precise numeric answers with a short explanation.",
            [g.tool("calculator", "Evaluates a math expression.", g.param("expression", "string", "Expression to evaluate"))],
            "A contractor bills $92/hr and works 37.5 hours per week for 6 weeks. What is the total invoice amount? Use the calculator.",
            ["Compute total invoice amount.", "Answer with the total briefly."],
            "Use the calculator once, then report the total as dollars.",
            "calculator",
            [("expression", "92*37.5*6")],
            "res1",
            "92*37.5*6 = 20700",
            "Use the computed value directly and format it as a dollar total.",
            "note1",
            "Total invoice amount is $20,700.",
        ),
        (
            "You are a calculation assistant who returns precise numeric answers with a short explanation.",
            [g.tool("calculator", "Evaluates a math expression.", g.param("expression", "string", "Expression to evaluate"))],
            "A store had 348 purchases from 12,000 visits. What is the conversion rate (in %)? Use the calculator.",
            ["Compute conversion rate percentage.", "Report the percentage briefly."],
            "Use the calculator once, then report the rounded percent.",
            "calculator",
            [("expression", "(348/12000)*100")],
            "res1",
            "(348/12000)*100 = 2.9",
            "Convert the calculator output into a percentage statement.",
            "note1",
            "The conversion rate is 2.90%.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /docs/q2_product_recap.md and list the three most important takeaways.",
            ["Load the requested document excerpt.", "Summarize the key takeaways briefly."],
            "Use the file tool once, then condense the excerpt into a short summary.",
            "load_file",
            [("path", "/docs/q2_product_recap.md")],
            "res1",
            "Excerpt: onboarding time dropped 35% after guided setup, mobile crash rate is now under 0.5%, and Q3 priorities are enterprise SSO plus upgraded analytics dashboards.",
            "Extract the three outcomes directly and keep the wording brief.",
            "note1",
            "Main takeaways: onboarding time dropped about 35%, mobile crash rate is now under 0.5%, and Q3 priorities are enterprise SSO plus better analytics dashboards.",
        ),
        (
            "You are a web reference assistant who fetches a page and answers concisely.",
            [g.tool("fetch_url", "Fetches a webpage and returns the relevant passage.", g.param("url", "string", "URL to fetch"))],
            "Look up an authoritative HTTP caching reference and explain what `Cache-Control: no-store` means in 1-2 sentences.",
            ["Fetch an authoritative reference passage.", "Explain the directive briefly."],
            "Use one fetch step, then restate the definition concisely.",
            "fetch_url",
            [("url", "https://www.rfc-editor.org/rfc/rfc9111.html")],
            "res1",
            "Relevant passage: the no-store response directive indicates that a cache MUST NOT store any part of either the immediate request or the response and MUST NOT use the response to satisfy any other request.",
            "Use the reference wording directly and add the sensitive-data intuition.",
            "note1",
            "Cache-Control: no-store tells caches not to store any part of the request or response for reuse. It is typically used for sensitive data where leaving a cached copy would be inappropriate.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /docs/security_audit_apr.md and summarize the top three findings.",
            ["Load the requested document excerpt.", "Summarize the top findings briefly."],
            "Use the file tool once, then condense the excerpt into a short findings summary.",
            "load_file",
            [("path", "/docs/security_audit_apr.md")],
            "res1",
            "Excerpt: incomplete MFA enforcement for legacy admin accounts, critical dependencies missing recent security patches, and gaps in centralized logging/alerting that hinder incident response.",
            "Extract the findings directly and keep the wording tight.",
            "note1",
            "Top findings: MFA is incomplete for legacy admin accounts, critical dependencies are behind on security patches, and centralized logging/alerting is too weak for reliable incident response.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /docs/launch_checklist.md and summarize the highest-risk open items.",
            ["Load the requested document excerpt.", "Summarize the highest-risk open items briefly."],
            "Use the file tool once, then turn the excerpt into a short risk summary.",
            "load_file",
            [("path", "/docs/launch_checklist.md")],
            "res1",
            "Excerpt: legal signoff pending, rollback owner unassigned, dashboards incomplete, support macros not finalized.",
            "State the open items directly and keep the answer brief.",
            "note1",
            "Highest-risk open items: legal signoff is still pending, rollback ownership is unclear, dashboards are incomplete, and support preparation is unfinished.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /docs/design_feedback.md and summarize the repeated themes.",
            ["Load the requested document excerpt.", "Summarize the repeated themes briefly."],
            "Use the file tool once, then condense the excerpt into a short theme summary.",
            "load_file",
            [("path", "/docs/design_feedback.md")],
            "res1",
            "Excerpt: navigation is dense, empty states are unclear, and saved views need stronger defaults.",
            "Pull out the repeated themes directly and keep the language tight.",
            "note1",
            "Repeated themes: navigation feels dense, empty states are unclear, and saved-view defaults need improvement.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /docs/pricing_review.md and summarize the recommendation.",
            ["Load the requested document excerpt.", "Summarize the recommendation briefly."],
            "Use the file tool once, then report the recommendation tightly.",
            "load_file",
            [("path", "/docs/pricing_review.md")],
            "res1",
            "Excerpt: keep annual discount, test a higher entry tier, simplify add-ons, avoid immediate enterprise repricing.",
            "Turn the excerpt into one concise recommendation sentence.",
            "note1",
            "Recommendation: keep the annual discount, test a higher entry tier, simplify add-ons, and avoid a large enterprise repricing right now.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Open /reports/security_audit_apr2026.txt and summarize the key findings in 4 bullets.",
            ["Load the requested report excerpt.", "Summarize the key findings briefly."],
            "Use the file tool once, then condense the excerpt into a short findings summary.",
            "load_file",
            [("path", "/reports/security_audit_apr2026.txt")],
            "res1",
            "Excerpt: MFA gaps on 3 admin accounts; 12 critical vulnerabilities unpatched >30 days on two public servers; SIEM missing logs from payment service and VPN; backup restore test failed for finance database.",
            "Extract the concrete findings directly and keep the summary compact.",
            "note1",
            "Key findings: MFA gaps remain on some admin accounts, several critical vulnerabilities are overdue on public servers, SIEM coverage is missing logs from payment and VPN systems, and the finance database restore test failed.",
        ),
        (
            "You are a document assistant who reads a file and returns a short, concrete summary.",
            files,
            "Please open /docs/security_audit_apr.md and summarize the key findings in 3 bullets.",
            ["Load the requested document excerpt.", "Summarize the key findings briefly."],
            "Use the file tool once, then distill the excerpt into a short findings summary.",
            "load_file",
            [("path", "/docs/security_audit_apr.md")],
            "res1",
            "Excerpt: incomplete MFA enforcement for legacy admin accounts, critical dependencies missing recent security patches, and gaps in centralized logging/alerting that hinder incident response.",
            "Extract the concrete findings directly and keep the answer compact.",
            "note1",
            "Key findings: MFA is incomplete for some legacy admin accounts, critical dependencies still need security patches, and centralized logging/alerting is too weak for strong incident response.",
        ),
    ]
    for item in nonrust_single:
        traces.append(g.single_tool_trace(*item))

    nonrust_multi = [
        (
            "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
            ci,
            "Our nightly integration tests started timing out in the container startup phase. What should I check first?",
            [
                "Pull the most relevant recent logs or failure output.",
                "Use one fallback source only if the primary source fails or is insufficient.",
                "Provide the first concrete investigation angle.",
            ],
            "Start with direct evidence, use one fallback at most, then answer succinctly.",
            "get_ci_logs",
            [("run_id", "nightly-failing-run-18422")],
            "logs1",
            "Error: CI log service unavailable",
            "If live logs fail or are too thin, use one fallback source to avoid over-searching.",
            "note_logs",
            "fetch_cached_incident",
            [("service", "test-runner")],
            "aux1",
            "Cached incident note: timeouts commonly occur when the container never becomes ready due to a failing healthcheck or slow image pull from the registry.",
            "Use the fallback note to recommend one focused next check rather than a long list.",
            "note_aux",
            "Check container readiness first: image pull latency/auth, the startup healthcheck itself, and any recent CPU or memory limit changes that would delay boot. This recommendation is based on the cached incident note because live logs were unavailable.",
        ),
        (
            "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
            ci,
            "Our deploy pipeline started failing at the unit-tests stage after a dependency bump. What should I check first?",
            [
                "Pull the most relevant recent logs or failure output.",
                "Use a second tool step only if it sharpens the diagnosis.",
                "Provide the first concrete investigation angle.",
            ],
            "Start with logs, then use one focused code-search step if needed.",
            "get_ci_logs",
            [("run_id", "deploy-failing-run-18422")],
            "logs1",
            "Run: 18422; FAIL: Cannot find module `left-pad` in test/bootstrap.js after dependency bump.",
            "The first error already points to a broken import path, so use one search step to locate it quickly.",
            "note_logs",
            "code_search",
            [("query", "left-pad")],
            "aux1",
            "1 match: repo/test/bootstrap.js imports `left-pad` directly.",
            "Use the search hit to recommend fixing the import or package version before broader debugging.",
            "note_aux",
            "Start with the first failing import in the unit-test logs: the dependency bump likely changed a package name or entrypoint. Check the import in test/bootstrap.js, verify the lockfile changed consistently, and pin or revert the bump if you need a quick unblock.",
        ),
        (
            "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
            ci,
            "Our integration tests intermittently time out only on main branch runs. What should we look at first?",
            [
                "Pull the most relevant recent logs or failure output.",
                "Use one fallback source only if the primary source fails or is insufficient.",
                "Provide the first concrete investigation angle.",
            ],
            "Start with direct evidence, use one fallback at most, then answer succinctly.",
            "get_ci_logs",
            [("run_id", "main-failing-run-18422")],
            "logs1",
            "Error: CI log service unavailable",
            "If live logs fail or are too thin, use one fallback source to avoid over-searching.",
            "note_logs",
            "fetch_cached_incident",
            [("service", "ci")],
            "aux1",
            "Cached incident note: main-branch timeouts frequently traced to runner pool saturation and occasional DNS failures during dependency setup.",
            "Use the fallback note to recommend one concrete infrastructure-first check.",
            "note_aux",
            "First check whether main runs are landing on more saturated runners or a different runner class, then verify DNS/network reliability during dependency setup. The main-only pattern makes infrastructure skew more likely than a deterministic test bug.",
        ),
        (
            "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
            ci,
            "Our deploys to staging fail intermittently with a permission denied error. Where should we look first?",
            [
                "Pull the most relevant recent logs or failure output.",
                "Use one supporting lookup only if it sharpens the diagnosis.",
                "Provide the first concrete investigation angle.",
            ],
            "Start with logs and use one targeted follow-up if needed.",
            "get_ci_logs",
            [("run_id", "staging-failing-run-18422")],
            "logs1",
            "Staging deploy job failed while fetching secret staging/DB_PASSWORD; runner role missing `secrets.read`.",
            "The logs already indicate an access problem, so use one supporting incident note only to confirm the common root cause.",
            "note_logs",
            "fetch_cached_incident",
            [("service", "staging-deploy")],
            "aux1",
            "Cached incident note: similar failures came from a policy rollout that removed secret read access in one namespace.",
            "Use the incident note to keep the recommendation focused on IAM or service-account permissions.",
            "note_aux",
            "Look first at the deploy runner’s IAM or service-account permissions for the secrets backend. The logs already point to denied secret access, so confirm the runner role and namespace policy before investigating app code.",
        ),
        (
            "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
            ci,
            "Our nightly pipeline started failing after a merge, but reruns usually pass. What should I check first?",
            [
                "Pull the most relevant recent logs or failure output.",
                "Use one fallback source only if the primary source fails or is insufficient.",
                "Provide the first concrete investigation angle.",
            ],
            "Start with direct evidence, use one fallback at most, then answer succinctly.",
            "get_ci_logs",
            [("run_id", "nightly-failing-run-18422")],
            "logs1",
            "Error: CI log service returned 503",
            "If live logs fail or are too thin, use one fallback source to avoid over-searching.",
            "note_logs",
            "fetch_cached_incident",
            [("service", "pipeline")],
            "aux1",
            "Cached incident note: flaky nightly failures that pass on rerun are frequently caused by transient dependency resolution or external registry hiccups.",
            "Use the fallback note to focus on transient external dependencies rather than code first.",
            "note_aux",
            "Check whether the failure happens during dependency or artifact fetches and whether versions are pinned. If reruns usually pass, transient external fetches or unpinned dependencies are a stronger first suspect than deterministic code regressions.",
        ),
        (
            "You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.",
            math,
            "Differentiate x^4 * ln(x), then verify the derivative by a second tool step and keep the answer concise.",
            [
                "Differentiate the expression.",
                "Verify the derivative by a second tool step.",
                "State the final derivative briefly.",
            ],
            "Use one differentiation step, one verification step, then stop.",
            "solve_symbolic",
            [("expression", "x^4 * ln(x)"), ("operation", "differentiate"), ("variable", "x")],
            "d1",
            "Computed derivative: 4*x^3*ln(x) + x^3",
            "The derivative result is already simple; verify it rather than adding another transform.",
            "note1",
            "derivative_check",
            [("candidate_antiderivative", "(x^4*ln(x))"), ("target_expression", "4*x^3*ln(x) + x^3"), ("variable", "x")],
            "chk1",
            "Differentiating x^4*ln(x) yields 4*x^3*ln(x) + x^3.",
            "The verification matches, so the final answer can just state the derivative cleanly.",
            "note2",
            "The derivative is 4x^3 ln(x) + x^3.",
        ),
        (
            "You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.",
            math,
            "Integrate 6*x - 3 + 2/x, verify it by differentiation, and keep the answer concise.",
            [
                "Compute an antiderivative.",
                "Verify it by differentiation.",
                "State the final answer briefly.",
            ],
            "Use one symbolic solve step, one derivative check, then stop.",
            "solve_symbolic",
            [("expression", "6*x - 3 + 2/x"), ("operation", "integrate"), ("variable", "x")],
            "int1",
            "Computed antiderivative: 3*x^2 - 3*x + 2*ln(x) + C",
            "The antiderivative is already simple; verify it directly rather than adding extra transforms.",
            "note1",
            "derivative_check",
            [("candidate_antiderivative", "3*x^2 - 3*x + 2*ln(x)"), ("target_expression", "6*x - 3 + 2/x"), ("variable", "x")],
            "chk1",
            "Derivative equals 6*x - 3 + 2/x.",
            "The derivative check confirms correctness, so the final answer can stay short.",
            "note2",
            "Antiderivative: 3x^2 - 3x + 2 ln(x) + C. Differentiating gives 6x - 3 + 2/x.",
        ),
        (
            "You are a planning assistant that helps product teams build realistic launch plans and concise schedules.",
            plans,
            "We need a 3-week rollout plan for an in-app onboarding checklist update. Pull major tasks, confirm the team can staff it, and keep it concise.",
            [
                "Check team availability for the 3-week window.",
                "Generate a baseline work breakdown.",
                "Provide a concise schedule recommendation.",
            ],
            "Get staffing first, then a minimal work breakdown, then summarize feasibility.",
            "get_availability",
            [("team_list", "ava,ben,chen,dina"), ("start_date", "2026-07-06"), ("end_date", "2026-07-26")],
            "avail1",
            "Availability: ava 60%, ben 40%, chen 70%, dina 50% for the 3-week window.",
            "Availability looks workable; now get a minimal breakdown sized to the short timeline.",
            "note1",
            "create_project_plan",
            [("project_name", "in-app onboarding checklist update"), ("objectives", "ship updated checklist copy, triggers, analytics, and QA"), ("timeline_weeks", "3")],
            "plan1",
            "Plan ID plan_onb_v1: requirements and copy, trigger logic, UI updates, analytics events, QA and rollout.",
            "With staffing and tasks in hand, give a simple sequencing recommendation instead of adding more tool steps.",
            "note2",
            "The team can likely cover this in 3 weeks if work starts with requirements and copy, then trigger logic and UI in parallel, followed by analytics wiring and a short QA/rollout window.",
        ),
        (
            "You are a planning assistant that helps product teams build realistic launch plans and concise schedules.",
            plans,
            "We need a 4-week launch plan for a billing export CSV improvement. Check team availability, generate the task breakdown, and keep the final recommendation concise.",
            [
                "Check team availability for the 4-week window.",
                "Generate the task breakdown.",
                "Provide a concise schedule recommendation.",
            ],
            "Get staffing first, then a baseline task breakdown, then stop with a short recommendation.",
            "get_availability",
            [("team_list", "maya,liam,noor,oscar"), ("start_date", "2026-08-04"), ("end_date", "2026-09-01")],
            "avail1",
            "Availability: maya 70%, liam 50%, noor 80%, oscar 40% for the 4-week window.",
            "Availability is enough to scope the next planning step; now get a compact work breakdown.",
            "note1",
            "create_project_plan",
            [("project_name", "billing export CSV improvement"), ("objectives", "fix column consistency, header naming, duplicate handling, and rollout docs"), ("timeline_weeks", "4")],
            "plan1",
            "Plan ID plan_csv_v1: requirements and field audit, export generator changes, duplicate handling, QA with sample customers, rollout docs.",
            "With staffing and tasks available, the final answer should just recommend a simple sequence.",
            "note2",
            "The team can likely deliver this in 4 weeks by starting with requirements and field audit, then export-generator changes, followed by duplicate handling, QA, and a short rollout-docs finish.",
        ),
        (
            "You are a Git assistant who gives compact, practical guidance.",
            git,
            "My PR branch won't push because it says non-fast-forward. I don't want to lose my local commits. What should I do?",
            [
                "Inspect repo state to confirm divergence.",
                "Inspect recent history to understand local vs remote commits.",
                "Provide a safe integration sequence that preserves local work.",
            ],
            "Check branch state, check recent commits, then recommend a safe rebase-or-merge path.",
            "git_status",
            [("repo_path", "./")],
            "st1",
            "On branch feature/pr-42. Your branch and origin/feature/pr-42 have diverged, and have 3 and 2 different commits each. Working tree clean.",
            "The branch has diverged, so check recent local and remote commits before recommending the next command.",
            "note1",
            "git_log",
            [("repo_path", "./"), ("limit", "8")],
            "log1",
            "local HEAD: abc1234 Add validation for empty inputs; bcd2345 Refactor request parsing. origin/feature/pr-42: def4567 Fix CI by pinning action versions; efg5678 Adjust lint config.",
            "With divergence confirmed, recommend fetch plus rebase as the safest default when local commits must be preserved.",
            "note2",
            "Fetch the remote branch, then rebase your local commits on top of it so you keep your work while integrating the remote changes. If conflicts appear, resolve them commit by commit, run tests, then push the rebased branch with --force-with-lease.",
        ),
    ]
    for item in nonrust_multi:
        traces.append(g.multi_tool_trace(*item))

    extra_rust_no_tool = [
        ("Why would you use `BTreeMap` instead of `HashMap` in Rust?", "Explain when BTreeMap is the better default.", "Tie the answer to ordering and range queries.", "Keep it focused on deterministic ordering and ordered-key operations.", "Use `BTreeMap` when you need keys in sorted order, predictable iteration order, or efficient range queries. `HashMap` is usually better for raw average-case lookup speed when ordering does not matter.", "note_btreemap"),
        ("Why is `Pin` mostly relevant for self-referential or async state machines?", "Explain the problem Pin is solving.", "Connect it to values that must not move after references into them exist.", "Keep it centered on movement invalidating internal references.", "`Pin` matters when moving a value would invalidate internal self-references or assumptions baked into generated state machines, such as some futures. It lets code rely on the value staying at a stable memory location after pinning.", "note_pin"),
        ("Why does Rust prefer `&str` parameters over `&String` in many APIs?", "Explain the API design reason briefly.", "Tie it to accepting the more general borrowed string view.", "State that `&str` accepts more callers and avoids needless restriction.", "`&str` is the better parameter type because it accepts both string slices and borrowed `String` values, so the API is more general without losing usefulness. `&String` is usually an unnecessary restriction.", "note_str_param"),
        ("Why is `VecDeque` sometimes better than `Vec`?", "Explain the main data-structure tradeoff briefly.", "Connect it to front insertion and removal costs.", "Keep it centered on queue-like workloads.", "`VecDeque` is better when you need efficient pushes and pops at both ends, especially queue-like workloads. `Vec` is still better when most operations are append/index and you want the simplest contiguous layout.", "note_vecdeque"),
        ("Why do Rust builders often take `self` and return `Self` instead of using `&mut self`?", "Explain the ergonomic reason briefly.", "Tie it to chaining and ownership of intermediate states.", "Keep the answer short and focused on fluent APIs.", "Taking `self` and returning `Self` makes builder chaining simple and keeps ownership moves explicit. `&mut self` also works, but value-consuming builders can be cleaner when intermediate states should not be reused accidentally.", "note_builder_self"),
        ("Why is `Option<Result<T, E>>` different from `Result<Option<T>, E>`?", "Explain the semantic difference briefly.", "Tie it to whether absence is an error or a normal outcome.", "Keep it focused on which layer is optional versus fallible.", "`Option<Result<T, E>>` means the whole operation may be absent, and if it is present it may succeed or fail. `Result<Option<T>, E>` means the operation itself ran and may fail, but absence of a value is a normal successful outcome.", "note_option_result"),
        ("Why can `?` only be used when the surrounding function can propagate a compatible error or residual type?", "Explain the main restriction briefly.", "Connect it to early return semantics.", "Keep it focused on `?` being syntax for propagating failure out of the current function.", "`?` works by returning early from the current function when an error or other residual appears, so the surrounding return type must know how to carry that residual. If the function cannot represent the propagated failure, `?` has nowhere valid to send it.", "note_question_mark"),
        ("Why might you prefer slices like `&[T]` in APIs over `&Vec<T>`?", "Explain the API design reason briefly.", "Tie it to accepting any contiguous borrowed sequence view.", "State that slices are more general than vectors for read-only access.", "`&[T]` is better because it accepts vectors, arrays, and other slice-producing containers while still expressing read-only indexed access. `&Vec<T>` unnecessarily couples the API to one concrete container.", "note_slice_api"),
        ("Why is `Arc<str>` useful in some read-heavy applications?", "Explain the main tradeoff briefly.", "Connect it to shared immutable text ownership.", "Keep it centered on deduplicated immutable strings shared across tasks.", "`Arc<str>` is useful when many tasks need shared ownership of the same immutable string data without repeated cloning of full `String` buffers. It trades mutability for cheap shared ownership and lower copy cost.", "note_arc_str"),
        ("Why can a `move` closure still borrow data indirectly through owned smart pointers?", "Explain the conceptual point briefly.", "Tie it to moving ownership of the pointer, not necessarily copying the underlying data.", "Keep it focused on what `move` actually moves.", "A `move` closure captures ownership of the values it closes over, but that may just mean moving a pointer-like owner such as `Arc` or `Rc`. The closure owns the handle, while the underlying data can still be shared or indirectly borrowed through that handle.", "note_move_closure"),
        ("Why is `tokio::select!` useful in async Rust?", "Explain the main purpose briefly.", "Tie it to waiting on multiple asynchronous events.", "Keep the answer centered on racing or coordinating futures.", "`tokio::select!` lets an async task wait on multiple futures at once and continue with whichever branch becomes ready first. It is useful for cancellation, timeouts, and coordinating concurrent events without blocking.", "note_select"),
        ("Why is `Bytes` often preferred over `Vec<u8>` in networking code?", "Explain the main performance reason briefly.", "Connect it to cheap cloning and slicing of shared buffers.", "Keep it focused on buffer sharing.", "`Bytes` is often better because it supports cheap cloning and slicing of shared immutable buffer storage, which is common in networking stacks. `Vec<u8>` is still great for unique mutable ownership, but it is less convenient for shared buffer views.", "note_bytes"),
        ("Why are trait bounds on generic functions sometimes better than using trait objects?", "Explain the main tradeoff briefly.", "Tie it to static dispatch and optimization.", "Keep the answer short and focused on compile-time specialization.", "Generic trait bounds keep static dispatch, which often means better optimization and no dynamic dispatch cost. Trait objects are better when you need heterogeneous runtime polymorphism or looser API boundaries.", "note_generic_bounds"),
        ("Why do many Rust APIs return iterators instead of allocating collections immediately?", "Explain the main design advantage briefly.", "Tie it to laziness and composability.", "Keep it focused on avoiding unnecessary allocation and enabling chaining.", "Returning iterators keeps work lazy, avoids immediate allocation, and makes it easy for callers to compose filtering, mapping, and collection decisions themselves. It gives callers more control over cost and output shape.", "note_iterators"),
        ("Why can `serde` structs benefit from `#[serde(default)]`?", "Explain the main configuration compatibility reason briefly.", "Tie it to missing fields in older or partial input.", "Keep it focused on resilient decoding.", "`#[serde(default)]` helps when some input fields may be omitted, such as older config files or partial payloads. It lets deserialization fill in a reasonable default instead of failing immediately on every missing field.", "note_serde_default"),
        ("Why do people use `thiserror` for application error enums?", "Explain the practical benefit briefly.", "Tie it to reducing boilerplate without hiding structure.", "Keep it centered on readable error types.", "`thiserror` makes custom error enums easier to write by generating common trait implementations while still keeping the error structure explicit in your code. It reduces boilerplate without forcing a boxed or opaque error model.", "note_thiserror"),
        ("Why does `PhantomData` exist in Rust?", "Explain the core purpose briefly.", "Connect it to type- and lifetime-level relationships not stored at runtime.", "Keep it focused on expressing ownership or variance information to the compiler.", "`PhantomData` lets a type tell the compiler about ownership, variance, or lifetime relationships that are logically present even when no runtime field stores that data. It is mainly about correct type-system behavior, not runtime state.", "note_phantomdata"),
        ("Why might a library expose `AsRef<Path>` for path parameters?", "Explain the ergonomic reason briefly.", "Tie it to accepting multiple path-like caller types.", "Keep it focused on flexible path inputs.", "`AsRef<Path>` makes a path-taking API flexible because callers can pass `&str`, `String`, `Path`, or `PathBuf` without extra conversion boilerplate. It widens usability while still normalizing to path semantics internally.", "note_asref_path"),
        ("Why is `usize` used for indexing collections in Rust?", "Explain the practical reason briefly.", "Tie it to pointer-sized indexing.", "Keep the answer short and direct.", "`usize` is the natural type for collection indices because it matches the machine’s pointer-sized address space. That makes it suitable for indexing memory-backed structures and avoids needless casts at the system boundary.", "note_usize_index"),
        ("Why do async traits often need boxing or macro support today?", "Explain the current limitation briefly.", "Tie it to trait method return types for async state machines.", "Keep it focused on object safety and generated future types.", "Async trait methods produce hidden future types, which complicates trait object safety and explicit return typing. Boxing or helper macros smooth over that mismatch by erasing or generating the otherwise awkward future types.", "note_async_traits"),
        ("Why does Rust distinguish `Copy` from `Clone`?", "Explain the semantic difference briefly.", "Tie it to implicit versus explicit duplication.", "Keep it short and focused on control of duplication semantics.", "`Copy` means a value can be duplicated implicitly with simple bitwise copy semantics, while `Clone` is an explicit operation that may run code or allocate. Rust separates them so implicit copies stay cheap and unsurprising.", "note_copy_clone"),
        ("Why is `SmallVec` sometimes used in hot Rust code paths?", "Explain the main optimization idea briefly.", "Tie it to avoiding heap allocation for small common cases.", "Keep the answer centered on inline storage.", "`SmallVec` can store a small number of elements inline, which avoids heap allocation for common short cases. It is useful in hot paths where most values stay small and allocation overhead matters.", "note_smallvec"),
        ("Why is `Cow<'a, [u8]>` useful for binary transforms?", "Explain the main benefit briefly.", "Tie it to borrowed fast paths with owned slow paths.", "Keep the answer short and focused on conditional copying.", "`Cow<'a, [u8]>` is useful when many binary transforms can pass the original bytes through unchanged, but some cases need a modified owned buffer. It avoids copying on the borrowed fast path while still supporting edits when needed.", "note_cow_bytes"),
        ("Why do people wrap shared mutable maps in a dedicated type instead of exposing `Arc<Mutex<HashMap<...>>>` everywhere?", "Explain the API design reason briefly.", "Tie it to encapsulation and invariant control.", "Keep it focused on narrowing the concurrency surface area.", "A dedicated wrapper type keeps locking and invariant logic in one place instead of leaking synchronization details through the whole codebase. That makes callers simpler and reduces the chance of inconsistent lock usage or ad hoc mutation patterns.", "note_wrapper_type"),
        ("Why is `OnceLock` useful in Rust?", "Explain the main use case briefly.", "Tie it to one-time initialization of shared state.", "Keep it focused on lazy shared setup.", "`OnceLock` is useful when some shared value should be initialized at most once and then read cheaply afterward. It gives a simple, safe pattern for lazy global or shared setup without repeated locking on the fast path.", "note_oncelock"),
        ("Why do some Rust APIs return `impl Iterator<Item = Result<T, E>>` instead of `Result<Vec<T>, E>`?", "Explain the streaming tradeoff briefly.", "Tie it to incremental consumption and partial progress.", "Keep it focused on laziness and not buffering everything eagerly.", "Returning `impl Iterator<Item = Result<T, E>>` allows incremental processing, early stopping, and lower memory use because callers do not have to buffer every item up front. `Result<Vec<T>, E>` is simpler when you truly need the whole successful collection at once.", "note_iter_result"),
        ("Why can using `collect::<Result<Vec<_>, _>>()` be convenient?", "Explain the main ergonomic reason briefly.", "Tie it to combining iteration with early error propagation.", "Keep it focused on collapsing many item results into one collection result.", "It is convenient because it turns an iterator of per-item results into one `Result<Vec<_>, _>`, collecting all successes until the first error. That matches the common pattern of building a collection while failing early on bad input.", "note_collect_result"),
        ("Why is `Arc<dyn Trait + Send + Sync>` common at service boundaries?", "Explain the design reason briefly.", "Tie it to shared runtime polymorphism across threads.", "Keep it short and focused on injectable shared behavior.", "It is common because it gives shared ownership of a thread-safe trait object, which is useful for injecting pluggable behavior like clients, stores, or policy implementations across async tasks and worker threads.", "note_arc_dyn"),
        ("Why is `std::mem::replace` useful when updating a field in place?", "Explain the main ownership reason briefly.", "Tie it to moving out while leaving a valid replacement behind.", "Keep it focused on satisfying Rust’s move rules.", "`std::mem::replace` lets you move a value out of a place while immediately putting another valid value back. That is useful when you need ownership of the old field but must keep the parent structure valid the whole time.", "note_replace"),
        ("Why can `Box<dyn Error>` be fine for binaries but less ideal for reusable libraries?", "Explain the tradeoff briefly.", "Tie it to convenience versus preserving structured error information.", "Keep it short and practical.", "`Box<dyn Error>` is convenient in binaries because it simplifies wiring many failure paths into one top-level error channel. Libraries often prefer concrete error types so callers can match, inspect, and handle failures more precisely.", "note_box_error"),
    ]
    for user, todo, rationale, think, response, tag in extra_rust_no_tool:
        traces.append(
            g.no_tool_trace(
                "You are a Rust language assistant who gives compact conceptual explanations.",
                user,
                todo,
                rationale,
                think,
                response,
                tag,
            )
        )

    extra_rust_doc_items = [
        ("std::mem::replace", "Replaces the value at a mutable location and returns the previous value.", "Explain what it does briefly.", "Mention that the old value is returned while the slot receives the replacement.", "std::mem::replace swaps in a new value at a mutable location and returns the old value without dropping either during the replacement step."),
        ("std::mem::swap", "Swaps the values at two mutable locations.", "Explain what it does briefly.", "State that it exchanges two values in place.", "std::mem::swap exchanges the values behind two mutable references in place, which is useful when you want both values preserved but moved to each other’s positions."),
        ("Option::as_ref", "Converts from &Option<T> to Option<&T>.", "Explain what it does briefly.", "Highlight that it borrows the inner value instead of moving it.", "Option::as_ref turns a borrowed Option into an Option of borrowed contents, so you can inspect the inner value without taking ownership."),
        ("Option::as_mut", "Converts from &mut Option<T> to Option<&mut T>.", "Explain what it does briefly.", "Highlight that it gives mutable access to the inner value if present.", "Option::as_mut lets you mutate the value inside an Option in place when it exists, without moving the Option itself."),
        ("Option::transpose", "Transposes an Option<Result<T, E>> into a Result<Option<T>, E>.", "Explain what it does briefly.", "Describe it as flipping the nesting between Option and Result.", "Option::transpose flips an Option<Result<T, E>> into Result<Option<T>, E>, which is useful when optional work may fail but absence itself is not an error."),
        ("Result::map_err", "Maps a Result<T, E> to Result<T, F> by applying a function to the error value.", "Explain what it does briefly.", "Focus on transforming errors while leaving successes untouched.", "Result::map_err changes only the error side of a Result, which is useful when adapting lower-level failures into your own error type."),
        ("Result::ok", "Converts a Result<T, E> into an Option<T>, discarding the error if any.", "Explain what it does briefly.", "Mention that errors are dropped intentionally.", "Result::ok turns a Result into an Option by keeping successful values and dropping error details, which is only appropriate when the error information is no longer needed."),
        ("Iterator::enumerate", "Creates an iterator yielding pairs of each item with its running index.", "Explain what it does briefly.", "Mention that indices start at zero.", "Iterator::enumerate pairs each yielded item with a zero-based running index, which is useful when iteration needs positional context."),
        ("Iterator::filter_map", "Creates an iterator that both filters and maps in one pass.", "Explain what it does briefly.", "Explain that None drops an item and Some emits a transformed value.", "Iterator::filter_map lets a closure skip items with None or emit transformed values with Some, combining filtering and mapping in one pass."),
        ("Iterator::find_map", "Applies a function and returns the first non-None result.", "Explain what it does briefly.", "Frame it as search plus transformation.", "Iterator::find_map searches until the closure returns Some, then stops and returns that transformed value. It combines lookup and conversion in one iterator step."),
        ("Iterator::collect::<HashMap<_, _>>", "Collects key-value pairs from an iterator into a HashMap.", "Explain what it does briefly.", "Mention that later duplicate keys overwrite earlier ones in standard collection behavior.", "Collecting into a HashMap builds a map from iterator key-value pairs. If the iterator yields duplicate keys, later values replace earlier ones."),
        ("Vec::drain", "Creates an iterator that removes a range from the vector and yields the removed items.", "Explain what it does briefly.", "State that the elements are removed as they are yielded.", "Vec::drain removes a chosen range from the vector and yields those removed elements, which is useful when you need ownership of a chunk while shrinking the original vector."),
        ("Vec::retain", "Retains only the elements specified by a predicate.", "Explain what it does briefly.", "Describe it as in-place filtering.", "Vec::retain filters a vector in place by keeping only elements whose predicate returns true, without allocating a separate output vector."),
        ("slice::windows", "Returns overlapping contiguous windows of a slice.", "Explain what it does briefly.", "Mention that adjacent windows overlap.", "slice::windows yields overlapping fixed-size views into a slice, which is useful for adjacent comparisons and rolling analysis."),
        ("slice::chunks", "Returns non-overlapping contiguous chunks of a slice.", "Explain what it does briefly.", "Contrast it with windows by noting the chunks do not overlap.", "slice::chunks splits a slice into non-overlapping fixed-size pieces, making it useful for batch-style processing of contiguous data."),
        ("HashMap::entry", "Provides in-place entry access for a given key, enabling insert-or-update patterns.", "Explain what it does briefly.", "Mention that it avoids separate lookup and insert paths.", "HashMap::entry gives in-place access to a key’s slot so you can insert, update, or modify efficiently without repeating separate existence checks."),
        ("HashMap::get_mut", "Returns a mutable reference to the value corresponding to the key.", "Explain what it does briefly.", "State that it allows in-place mutation when the key exists.", "HashMap::get_mut returns mutable access to an existing value for a key, letting you update it in place without removing or reinserting the entry."),
        ("BTreeMap::range", "Creates an iterator over entries whose keys fall within a specified range.", "Explain what it does briefly.", "Tie it to ordered map traversal.", "BTreeMap::range iterates over only the entries whose keys lie within a chosen ordered range, which is one reason BTreeMap is useful when key order matters."),
        ("std::path::Path::join", "Creates a new path by appending a path segment.", "Explain what it does briefly.", "Mention that it uses path semantics rather than manual string concatenation.", "Path::join appends a path segment using filesystem path semantics, which is safer and clearer than manually concatenating path strings."),
        ("std::fs::read_to_string", "Reads an entire file into a String.", "Explain what it does briefly.", "Mention that it is convenient when the whole file comfortably fits in memory.", "std::fs::read_to_string reads a file fully into a String, which is convenient for smaller text files when streaming is unnecessary."),
        ("Arc::clone", "Clones an Arc by increasing the reference count to the same allocation.", "Explain what it does briefly.", "Emphasize that the data is shared, not deep-copied.", "Arc::clone creates another shared owner of the same allocation by incrementing the reference count; it does not deep-copy the underlying data."),
        ("Mutex::lock", "Acquires the mutex, blocking the current thread until the lock is available.", "Explain what it does briefly.", "Mention that it returns a guard controlling access to the protected data.", "Mutex::lock waits until exclusive access is available and then returns a guard, which grants access to the protected data until the guard is dropped."),
        ("RwLock::read", "Acquires shared read access to the lock-protected value.", "Explain what it does briefly.", "Mention that multiple readers may coexist.", "RwLock::read returns a shared read guard, allowing multiple readers at the same time as long as no writer holds the lock."),
        ("RwLock::write", "Acquires exclusive write access to the lock-protected value.", "Explain what it does briefly.", "Mention that it excludes both readers and other writers.", "RwLock::write returns an exclusive write guard, so it blocks until there are no active readers or writers."),
        ("std::iter::once", "Creates an iterator that yields a single element exactly once.", "Explain what it does briefly.", "Point out that it is useful for prepending or composing iterator pipelines.", "std::iter::once creates a one-item iterator, which is handy when you want to inject a single value into a larger iterator pipeline."),
        ("std::iter::repeat", "Creates an iterator that repeats the same value endlessly.", "Explain what it does briefly.", "Mention that callers usually pair it with take or zip.", "std::iter::repeat yields the same value forever, so it is usually combined with adapters like take when you need a bounded repeated source."),
        ("std::cmp::Reverse", "A wrapper type that reverses the ordering of the wrapped value.", "Explain what it does briefly.", "Tie it to sorting descending or making a min-heap from a max-heap structure.", "std::cmp::Reverse flips the ordering of a value, which is useful for descending sorts or for turning `BinaryHeap` behavior into a min-heap pattern."),
        ("std::time::Duration::from_secs", "Creates a Duration from a whole number of seconds.", "Explain what it does briefly.", "Keep it simple and direct.", "Duration::from_secs constructs a time span from an integer number of seconds, which is useful for readable timeout and interval configuration."),
        ("std::str::FromStr", "A trait for parsing a value from a string representation.", "Explain what it does briefly.", "Mention that many standard and custom types implement it.", "FromStr is the standard trait for turning text into a typed value, and many Rust types implement it so parsing can use a shared interface."),
        ("std::convert::TryFrom", "A trait for fallible conversions between types.", "Explain what it does briefly.", "Highlight that conversion may fail and returns a Result.", "TryFrom represents conversions that can fail, so implementing or using it expresses that not every source value maps cleanly into the target type."),
        ("std::ops::Deref", "A trait for transparent dereferencing behavior.", "Explain what it does briefly.", "Tie it to smart pointers acting like references to their targets.", "Deref lets pointer-like types behave like references to an inner target for method and operator access, which is why smart pointers often feel ergonomic to use."),
        ("std::cell::RefCell", "A cell type that enforces Rust’s borrowing rules at runtime instead of compile time.", "Explain what it does briefly.", "Mention interior mutability and runtime borrow checking.", "RefCell enables interior mutability by checking the borrowing rules at runtime, which is useful in single-threaded patterns that the static borrow checker cannot express directly."),
        ("std::cell::Cell", "A cell type for simple Copy values that supports interior mutation without borrowing references.", "Explain what it does briefly.", "Focus on small Copy data updated through shared access.", "Cell is useful for small Copy values when you need interior mutation through shared access and do not need references to the inner value."),
        ("std::sync::OnceLock", "A synchronization primitive for one-time initialization followed by shared reads.", "Explain what it does briefly.", "Mention lazy setup of shared state.", "OnceLock is for values that should be initialized once, often lazily, and then read cheaply by many callers afterward."),
        ("tokio::spawn", "Spawns an asynchronous task onto the Tokio runtime.", "Explain what it does briefly.", "Mention that the task runs concurrently with the caller.", "tokio::spawn schedules an async task to run concurrently on the Tokio runtime, allowing the caller to continue without waiting immediately for completion."),
        ("tokio::time::sleep", "Returns a future that completes after the given duration elapses.", "Explain what it does briefly.", "Mention it is non-blocking within async code.", "tokio::time::sleep yields a future that waits without blocking the executor thread, making it the standard async delay primitive in Tokio."),
        ("tokio::sync::mpsc", "Provides asynchronous multi-producer, single-consumer channels.", "Explain what it does briefly.", "Highlight async message passing between tasks.", "Tokio’s mpsc channels let multiple async tasks send values to one receiver, which is useful for coordination without shared mutable state."),
        ("serde_json::from_str", "Parses JSON text into a typed Rust value.", "Explain what it does briefly.", "Mention that the target type drives the parse shape.", "serde_json::from_str parses JSON text into whatever Rust type you ask for, as long as that type implements the necessary deserialization traits."),
        ("serde_json::to_string", "Serializes a Rust value into a JSON string.", "Explain what it does briefly.", "Mention that the value type controls the output structure.", "serde_json::to_string converts a Rust value into JSON text based on that value’s serialization implementation."),
        ("anyhow::Context", "Adds higher-level context to errors before propagating them.", "Explain what it does briefly.", "Tie it to making failure chains easier to understand.", "anyhow::Context lets you attach human-useful context to an error before returning it, which makes higher-level failure messages much easier to diagnose."),
        ("tracing::instrument", "An attribute macro that creates tracing spans around function calls.", "Explain what it does briefly.", "Mention that it helps correlate logs with function execution.", "tracing::instrument adds a span around a function call, which helps structured logs and traces show which function invocation produced downstream events."),
        ("futures::stream::StreamExt::buffer_unordered", "Polls multiple stream-produced futures concurrently and yields results as they complete.", "Explain what it does briefly.", "Tie it to bounded concurrent async work.", "buffer_unordered lets a stream process several async operations concurrently while yielding each result as soon as it finishes, which is useful for bounded parallelism."),
        ("reqwest::Client", "A reusable HTTP client that manages connection pooling and configuration.", "Explain what it does briefly.", "Mention that callers typically reuse one client instead of rebuilding it per request.", "reqwest::Client is the reusable HTTP client handle that manages pooling and shared configuration, so applications usually create it once and reuse it for many requests."),
        ("sqlx::query!", "A macro that checks SQL queries against the expected schema at compile time or prepare time.", "Explain what it does briefly.", "Mention its stronger safety compared with raw stringly SQL execution.", "sqlx::query! gives stronger safety by checking query shapes against schema information, which reduces runtime surprises from mismatched columns or types."),
        ("clap::Parser", "A derive-based trait used to turn a struct into a command-line parser.", "Explain what it does briefly.", "Highlight that struct fields define CLI arguments.", "clap::Parser lets a struct describe command-line arguments declaratively, then derives the parsing logic from those field annotations."),
        ("axum::Router", "The main route-composition type in axum for building HTTP services.", "Explain what it does briefly.", "Mention that it combines routes, middleware, and shared state wiring.", "axum::Router is the central composition type for defining routes and layering middleware or shared state into an HTTP service."),
        ("tower::Service", "A trait representing an asynchronous request-response unit of work.", "Explain what it does briefly.", "Tie it to composable middleware and handlers.", "tower::Service is the core abstraction behind composable request handling and middleware in the Tower ecosystem, expressing async request-in, response-out behavior."),
        ("proptest::proptest!", "A macro for writing property-based tests.", "Explain what it does briefly.", "Mention that it generates many randomized inputs to test invariants.", "The `proptest!` macro defines property-based tests that exercise many generated inputs, which is useful for checking invariants beyond a few hand-picked examples."),
        ("insta::assert_snapshot!", "A macro for asserting that output matches a stored snapshot.", "Explain what it does briefly.", "Mention that snapshot updates are explicit and reviewable.", "insta::assert_snapshot! compares output against a stored snapshot so changes are visible and reviewable, which is useful for structured text or UI-like output tests."),
        ("std::fmt::Display", "A trait for user-facing string formatting.", "Explain what it does briefly.", "Contrast it implicitly with more debug-oriented formatting.", "Display is the trait for concise user-facing formatting, as opposed to more programmer-oriented debug output."),
        ("std::fmt::Debug", "A trait for programmer-facing formatting and diagnostics.", "Explain what it does briefly.", "Keep it short and direct.", "Debug is the trait for programmer-oriented formatting, usually used in logs, test failures, and diagnostic output rather than polished end-user messages."),
    ]
    for symbol, result_data, todo, think, response in extra_rust_doc_items:
        traces.append(
            g.single_tool_trace(
                "You are a Rust documentation assistant who answers briefly and precisely.",
                rd,
                f"Look up `{symbol}` in the docs tool and explain it briefly.",
                [f"Look up {symbol} in the docs tool.", todo],
                "Use one tool call, then summarize the behavior concisely.",
                "rustdoc_lookup",
                [("symbol", symbol)],
                "res1",
                result_data,
                think,
                "note1",
                response,
            )
        )

    extra_rust_debug_items = [
        ("My Tokio task captures `Rc<AppState>` and fails to spawn. What is the core issue?", "cargo check: future cannot be sent between threads safely; captured value has type Rc<AppState> which is not Send.", "Rc", "The task is crossing a multithreaded executor boundary with a non-Send captured type.", "The core issue is that `tokio::spawn` usually requires a Send future, but `Rc` is single-threaded and not Send. Replace shared `Rc` state with `Arc` or keep the task on a single-threaded local executor.", "cargo_check"),
        ("My `?` operator fails in a function returning `Option<T>`. Why?", "cargo check: the `?` operator can only be used on `Option`s, not on `Result<_, _>`, in a function that returns `Option<_>`.", "Result", "The surrounding return type cannot carry the propagated Result error directly.", "The failure happens because `?` is trying to propagate a `Result` error out of a function that only returns `Option`. Convert the `Result` into an `Option`, or change the function to return `Result` so the error can propagate properly.", "cargo_check"),
        ("I tried to collect references from a temporary iterator chain and got a lifetime error. What is the likely mistake?", "cargo check: temporary value dropped while borrowed.", "Iterator::collect", "The code is probably keeping references to data owned by a temporary that disappears too early.", "The likely mistake is collecting references that point into a temporary value or temporary iterator-produced buffer. Bind the owned data first or collect owned values instead of references tied to a short-lived temporary.", "cargo_check"),
        ("My `HashMap<&str, usize>` stores keys from parsed request bodies and now lifetimes explode. What is the conceptual fix?", "cargo check: borrowed value does not live long enough.", "String", "The map is trying to keep borrowed keys after the source text goes away.", "The conceptual fix is to own the keys instead of borrowing them from short-lived request buffers. Use `String` keys or otherwise ensure the source text outlives the map.", "cargo_check"),
        ("I used `tokio::time::sleep` inside a loop but forgot `.await`; the compiler complains. What is the real issue?", "cargo check: unused implementer of `Future` that must be used.", "tokio::time::sleep", "The sleep call creates a future, but the loop never polls or awaits it.", "The real issue is that `tokio::time::sleep` returns a future and nothing happens until it is awaited or otherwise polled. Add `.await` so the delay actually occurs.", "cargo_check"),
        ("My test comparing JSON strings keeps failing even though the data is equivalent. What is the likely mistake?", "cargo test failure: expected exact string match, but object field order differed.", "serde_json::Value", "The test is checking raw serialization form instead of structured JSON meaning.", "The likely mistake is asserting on raw JSON string order rather than parsed JSON structure. Compare parsed values or normalize serialization assumptions instead of depending on field order.", "cargo_test"),
        ("Clippy says this `clone()` is redundant after I switched to borrowing. What is the conceptual fix?", "cargo clippy: redundant clone.", "Clone", "The code is likely cloning data that is already available by shared reference.", "The fix is to follow the new ownership flow and use the borrowed value directly where possible. If the data is only being read, the extra `clone()` just adds cost without solving an ownership problem.", "cargo_clippy"),
        ("I tried to mutate a `HashMap` while iterating over it and hit a borrow error. Why?", "cargo check: cannot borrow `map` as mutable because it is also borrowed as immutable.", "HashMap::entry", "The iteration keeps an immutable borrow alive while mutation needs exclusive access.", "The error happens because iterating holds a borrow on the map while mutation requires exclusive access. Collect the keys first, restructure the algorithm, or use entry-based updates in a separate pass.", "cargo_check"),
        ("My `spawn_blocking` closure captures a borrowed reference and now the compiler wants `'static`. What is the issue?", "cargo check: borrowed data escapes outside of function; argument requires that borrowed value is borrowed for 'static.", "spawn_blocking", "The blocking task may outlive the current stack frame, so borrowed data cannot be captured directly.", "The issue is that `spawn_blocking` may run after the current function returns, so captured data usually needs to be owned and `'static`. Move owned values into the closure instead of borrowing stack data.", "cargo_check"),
        ("I switched a field to `Option<T>` but pattern matching still moves it out accidentally. What should I watch for?", "cargo check: cannot move out of `self.field` which is behind a mutable reference.", "Option::take", "The code is trying to move the value out directly instead of leaving a valid replacement behind.", "Watch for direct moves out of a borrowed field. `Option::take` is the usual fix because it moves the value out while leaving `None` behind in a valid state.", "cargo_check"),
        ("A trait object method call fails because the trait is not object safe. What usually causes that?", "cargo check: the trait cannot be made into an object.", "dyn Trait", "The trait probably uses methods or associated items that require knowing the concrete type at compile time.", "Traits are usually not object safe when some methods require concrete `Self` knowledge, generic methods, or incompatible associated item usage. If you need trait objects, redesign the trait so its callable surface works through dynamic dispatch.", "cargo_check"),
        ("My `Vec::retain` closure tries to push into the same vector and borrow checking fails. Why?", "cargo check: cannot borrow `items` as mutable more than once at a time.", "Vec::retain", "retain already holds mutable access to the vector while the closure runs.", "The closure runs while `retain` already has mutable control of the vector, so trying to mutate the same vector again conflicts with that borrow. Build side effects separately instead of mutating the vector from inside its own retain closure.", "cargo_check"),
        ("I tried to store an async closure in a struct field and the type got out of hand. What is the core design issue?", "cargo check: one type is more general than the other / expected opaque type, found a different opaque type.", "impl Trait", "Each async block or closure produces its own hidden future type, so storing them directly can become awkward.", "The core issue is that each async closure or block has its own unique hidden future type. If you need storage or heterogeneity, use boxing or a trait-object-based abstraction instead of expecting all async closures to share one concrete type.", "cargo_check"),
        ("My stream processor uses `buffer_unordered` but still behaves serially. What should I check?", "cargo test failure: processing order indicates only one future in flight at a time.", "buffer_unordered", "The concurrency limit may be one, or the upstream stream may itself yield work serially.", "Check the concurrency limit first and confirm the upstream stream is producing multiple futures before awaiting them. `buffer_unordered` only helps if there is actual overlap available to run.", "cargo_test"),
        ("I changed a config field from `String` to `&str` and deserialization now needs lifetimes everywhere. Why?", "cargo check: missing lifetime specifier / borrowed value does not live long enough.", "Deserialize", "Borrowed config fields tie the decoded value to the input buffer lifetime.", "Using `&str` means the deserialized struct now borrows from the original input text, so lifetimes have to flow through the whole type. `String` avoids that complexity by owning the decoded data.", "cargo_check"),
        ("My `BinaryHeap<Reverse<T>>` code is producing the opposite order from before. What is the conceptual reason?", "cargo test failure: expected max item first, got min item first.", "std::cmp::Reverse", "Wrapping keys in Reverse intentionally flips the ordering.", "The conceptual reason is that `Reverse` inverts the ordering, so a max-heap behaves like a min-heap over the wrapped values. If the test still expects max-heap order, the assertions need to change too.", "cargo_test"),
        ("I used `unwrap()` in a parser and now fuzzing finds panics. What is the design fix?", "cargo test failure: thread panicked at called `Option::unwrap()` on a `None` value.", "Option", "The parser is treating malformed input like an impossible state instead of an expected failure case.", "The design fix is to treat malformed input as normal fallible control flow by returning `Result` or `Option` explicitly, not by panicking. Parsers should surface bad input as data errors instead of crashing.", "cargo_test"),
        ("My derive-generated CLI parser rejects an environment variable default I expected. What should I inspect first?", "cargo test failure: expected default value from env, but argument remained unset.", "clap::Parser", "The derive metadata likely does not declare the env mapping the way the test assumes.", "Inspect the clap field attributes first, especially how the environment variable is declared and whether a default is separate from env loading. The parser behavior is usually driven directly by those derive annotations.", "cargo_test"),
        ("I made a service generic over a huge stack of middleware and compile times exploded. What is the conceptual tradeoff?", "cargo check: reached the recursion limit while instantiating types.", "tower::Service", "Static composition keeps zero-cost abstraction but can create enormous concrete types.", "The tradeoff is that deeply generic middleware stacks preserve static dispatch and optimization, but they can also create huge concrete types and longer compile times. At some point, boxing or type erasure can be a pragmatic relief valve.", "cargo_check"),
        ("My snapshot tests churn every run because timestamps change. What is the real fix?", "cargo test failure: snapshot mismatch due to timestamp fields.", "insta::assert_snapshot!", "The snapshot is recording nondeterministic fields that should be normalized first.", "The real fix is to normalize or redact nondeterministic fields like timestamps before snapshot assertion. Snapshot tests work best on stable output, not raw data with changing incidental fields.", "cargo_test"),
    ]
    for user, primary, doc_symbol, think, response, first_tool in extra_rust_debug_items:
        traces.append(
            g.multi_tool_trace(
                "You are a Rust debugging assistant who diagnoses compiler and tool output concisely.",
                cargo,
                user,
                [
                    "Get the primary diagnostic or tool output for the failure.",
                    "Use one targeted docs lookup if it sharpens the fix.",
                    "Give a concise diagnosis and repair direction.",
                ],
                "Use one concrete tool result, one supporting lookup, then answer without extra loops.",
                first_tool,
                [("crate_path", "./")],
                "step1",
                primary,
                think,
                "note1",
                "rustdoc_lookup",
                [("symbol", doc_symbol)],
                "step2",
                f"rustdoc: concise reference for {doc_symbol}.",
                "The diagnostic and the targeted doc reference are enough; stop after the answer.",
                "note2",
                response,
            )
        )

    extra_nonrust_single = [
        ("What was net-new ARR last quarter?", "SELECT COALESCE(SUM(new_arr) - SUM(churned_arr), 0) AS net_new_arr FROM quarterly_arr WHERE quarter = '2026-Q1';", "Query result: net_new_arr = 684000", "Net-new ARR last quarter was $684,000."),
        ("How many support tickets were opened with priority P1 last week?", "SELECT COUNT(*) AS p1_tickets_last_week FROM support_tickets WHERE priority = 'P1' AND created_at >= CURRENT_DATE - INTERVAL '7 days';", "Query result: p1_tickets_last_week = 14", "There were 14 P1 support tickets opened last week."),
        ("What was the average response time for chat support yesterday?", "SELECT AVG(first_response_minutes) AS avg_response_minutes FROM support_sessions WHERE started_at >= CURRENT_DATE - INTERVAL '1 day' AND started_at < CURRENT_DATE;", "Query result: avg_response_minutes = 6.4", "Average chat-support first response time yesterday was 6.4 minutes."),
        ("Open /docs/vendor_risk_review.md and summarize the recommendation.", "/docs/vendor_risk_review.md", "Excerpt: keep the vendor for now, require annual pen tests, tighten SLA language, and add data-retention deletion guarantees.", "Recommendation: keep the vendor for now, but require annual pen tests, stronger SLA language, and explicit data-deletion guarantees."),
        ("Open /docs/db_capacity_notes.md and summarize the main conclusion.", "/docs/db_capacity_notes.md", "Excerpt: primary risk is write IOPS saturation during end-of-month batching; short-term fix is queue smoothing; medium-term fix is storage class upgrade.", "Main conclusion: end-of-month batching risks write IOPS saturation, so the short-term fix is queue smoothing and the medium-term fix is a storage upgrade."),
        ("Open /docs/mobile_release_retro.md and summarize the top issues.", "/docs/mobile_release_retro.md", "Excerpt: crash-symbol upload was late, feature flags were not mirrored in staging, and release notes were finalized too close to ship time.", "Top issues: symbol upload lagged, staging flags drifted from production settings, and release notes were finalized too late."),
        ("Open /docs/incident_1184_summary.md and summarize the root cause.", "/docs/incident_1184_summary.md", "Excerpt: a stale DNS record kept one worker pool pointing at an old cache node after failover, causing high latency and retries.", "Root cause: a stale DNS record kept part of the worker pool pointed at an old cache node after failover, which drove latency and retries."),
        ("A customer prepays $18,500 and consumes $2,960 this month. What balance remains? Use the calculator.", "18500-2960", "18500-2960 = 15540", "Remaining balance is $15,540."),
        ("A team completed 87 of 96 migration checks. What percent is complete? Use the calculator.", "(87/96)*100", "(87/96)*100 = 90.625", "Progress is 90.63% complete."),
        ("A budget went from $420,000 to $483,000. What was the percentage increase? Use the calculator.", "((483000-420000)/420000)*100", "((483000-420000)/420000)*100 = 15", "The budget increased by 15%."),
    ]
    for prompt, expr_or_path, result_data, response in extra_nonrust_single:
        if prompt.startswith("Open /docs") or prompt.startswith("Open /reports") or prompt.startswith("Open /docs/incident"):
            traces.append(
                g.single_tool_trace(
                    "You are a document assistant who reads a file and returns a short, concrete summary.",
                    files,
                    prompt,
                    ["Load the requested document excerpt.", "Summarize the requested information briefly."],
                    "Use the file tool once, then condense the excerpt into a short summary.",
                    "load_file",
                    [("path", expr_or_path)],
                    "res1",
                    result_data,
                    "Extract the main conclusion directly and keep the wording tight.",
                    "note1",
                    response,
                )
            )
        elif "calculator" in prompt.lower() or "%" in prompt:
            traces.append(
                g.single_tool_trace(
                    "You are a calculation assistant who returns precise numeric answers with a short explanation.",
                    [g.tool("calculator", "Evaluates a math expression.", g.param("expression", "string", "Expression to evaluate"))],
                    prompt,
                    ["Compute the requested quantity.", "Answer with the result briefly."],
                    "Use the calculator once, then report the computed result.",
                    "calculator",
                    [("expression", expr_or_path)],
                    "res1",
                    result_data,
                    "Use the computed value directly and keep the answer concise.",
                    "note1",
                    response,
                )
            )
        else:
            traces.append(
                g.single_tool_trace(
                    "You are a data access assistant who uses SQL and answers briefly.",
                    sql,
                    prompt,
                    ["Run the requested query.", "Report the result briefly."],
                    "Use one SQL query, then answer with the returned figure.",
                    "run_sql",
                    [("query", expr_or_path)],
                    "res1",
                    result_data,
                    "The query result already contains the exact answer needed.",
                    "note1",
                    response,
                )
            )

    extra_nonrust_multi = [
        ("We need a 2-week rollout plan for a support-macro cleanup. Check staffing, generate the work breakdown, and keep it concise.", "mia,raj,toni", "2026-06-02", "2026-06-16", "support-macro cleanup", "rewrite macros, review tone, QA reply paths, stage rollout", "2", "Availability: mia 60%, raj 50%, toni 70% for the 2-week window.", "Plan ID plan_macro_v1: inventory macros, rewrite and review, QA high-volume flows, staged rollout.", "The team can likely deliver this in 2 weeks by inventorying macros first, rewriting and reviewing next, then running QA and a short staged rollout."),
        ("We need a 5-week rollout plan for an account-deletion flow update. Check staffing, generate the work breakdown, and keep it concise.", "alina,ben,casey,drew", "2026-09-01", "2026-10-06", "account-deletion flow update", "legal review, data deletion jobs, UI updates, support docs, QA and rollout", "5", "Availability: alina 60%, ben 70%, casey 50%, drew 65% for the 5-week window.", "Plan ID plan_delete_v1: legal requirements, deletion job updates, UI messaging, support docs, QA and rollout.", "The team can likely cover this in 5 weeks by starting with legal requirements and deletion-job updates, then handling UI and docs in parallel before QA and rollout."),
        ("My branch says non-fast-forward after the release branch moved. I need the safest next step without losing work.", "release/hotfix-19", "On branch hotfix/checkout-retry. Your branch and origin/hotfix/checkout-retry have diverged, and have 2 and 4 different commits each. Working tree clean.", "local HEAD: aa1100 Fix retry backoff; bb2200 Add checkout metrics. origin/hotfix/checkout-retry: cc3300 Patch release config; dd4400 Revert failing feature flag.", "Fetch the remote branch, then rebase your local commits on top of it if you want a clean history while preserving your work. Resolve conflicts, rerun tests, and push with --force-with-lease only after the rebase is verified."),
        ("Our deploy job started failing after an action-version change. What should I inspect first?", "deploy-run-29811", "Run: 29811; FAIL: action `acme/setup-node@v2` not found because the workflow references a removed tag.", "acme/setup-node", "1 match: .github/workflows/deploy.yml uses `acme/setup-node@v2`.", "Inspect the workflow reference first: the deploy job is likely pinned to a removed or renamed action tag. Update the action version deliberately, rerun the workflow, and only then investigate broader deploy logic."),
        ("Nightly ETL is timing out before transformation starts. What should I check first?", "etl-run-55102", "Error: CI log service unavailable", "etl", "Cached incident note: ETL startup delays usually come from warehouse credential rotation drift or exhausted worker queues before the job begins transformation.", "Check startup dependencies first: warehouse credentials, queue backlog, and whether workers are saturated before transformation starts. The cached incident note points to infrastructure prerequisites rather than transformation logic."),
        ("Differentiate x^5 - 4*x^2 + ln(x), verify it, and keep the answer concise.", "x^5 - 4*x^2 + ln(x)", "Computed derivative: 5*x^4 - 8*x + 1/x", "Differentiating x^5 - 4*x^2 + ln(x) yields 5*x^4 - 8*x + 1/x.", "The derivative is 5x^4 - 8x + 1/x."),
        ("Integrate 8*x + 1/x, verify it, and keep the answer concise.", "8*x + 1/x", "Computed antiderivative: 4*x^2 + ln(x) + C", "Derivative equals 8*x + 1/x.", "Antiderivative: 4x^2 + ln(x) + ln(x) - ln(x) + C.", "Antiderivative: 4x^2 + ln(x) + C. Differentiating gives 8x + 1/x."),
    ]
    for item in extra_nonrust_multi:
        prompt = item[0]
        if prompt.startswith("We need a"):
            user, team_list, start_date, end_date, project_name, objectives, weeks, avail_res, plan_res, response = item
            traces.append(
                g.multi_tool_trace(
                    "You are a planning assistant that helps product teams build realistic launch plans and concise schedules.",
                    plans,
                    user,
                    ["Check team availability for the requested window.", "Generate a baseline work breakdown.", "Provide a concise schedule recommendation."],
                    "Get staffing first, then a compact work breakdown, then stop with a short recommendation.",
                    "get_availability",
                    [("team_list", team_list), ("start_date", start_date), ("end_date", end_date)],
                    "avail1",
                    avail_res,
                    "Availability is enough to scope the next planning step; now get a compact breakdown.",
                    "note1",
                    "create_project_plan",
                    [("project_name", project_name), ("objectives", objectives), ("timeline_weeks", weeks)],
                    "plan1",
                    plan_res,
                    "With staffing and tasks in hand, finish with one short sequencing recommendation.",
                    "note2",
                    response,
                )
            )
        elif prompt.startswith("My branch"):
            user, repo_path, status_res, log_res, response = item
            traces.append(
                g.multi_tool_trace(
                    "You are a Git assistant who gives compact, practical guidance.",
                    git,
                    user,
                    ["Inspect repo state to confirm divergence.", "Inspect recent history to understand local vs remote commits.", "Provide a safe integration sequence that preserves local work."],
                    "Check branch state, check recent commits, then recommend a safe rebase path.",
                    "git_status",
                    [("repo_path", "./")],
                    "st1",
                    status_res,
                    "The branch has diverged, so inspect recent commits before recommending the next command.",
                    "note1",
                    "git_log",
                    [("repo_path", "./"), ("limit", "8")],
                    "log1",
                    log_res,
                    "With divergence confirmed, recommend the safest sequence that preserves local commits.",
                    "note2",
                    response,
                )
            )
        elif prompt.startswith("Our deploy job") or prompt.startswith("Nightly ETL"):
            if prompt.startswith("Our deploy job"):
                user, run_id, logs_res, query, search_res, response = item
                traces.append(
                    g.multi_tool_trace(
                        "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
                        ci,
                        user,
                        ["Pull the most relevant recent logs or failure output.", "Use one second tool step only if it sharpens the diagnosis.", "Provide the first concrete investigation angle."],
                        "Start with logs, then use one focused search step if needed.",
                        "get_ci_logs",
                        [("run_id", run_id)],
                        "logs1",
                        logs_res,
                        "The first error already points to a broken workflow reference, so search the codebase once to confirm it.",
                        "note1",
                        "code_search",
                        [("query", query)],
                        "aux1",
                        search_res,
                        "Use the search hit to keep the fix recommendation focused.",
                        "note2",
                        response,
                    )
                )
            else:
                user, run_id, logs_res, service, cached_res, response = item
                traces.append(
                    g.multi_tool_trace(
                        "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
                        ci,
                        user,
                        ["Pull the most relevant recent logs or failure output.", "Use one fallback source only if the primary source fails or is insufficient.", "Provide the first concrete investigation angle."],
                        "Start with direct evidence, use one fallback at most, then answer succinctly.",
                        "get_ci_logs",
                        [("run_id", run_id)],
                        "logs1",
                        logs_res,
                        "If live logs fail, use one fallback source instead of broad searching.",
                        "note1",
                        "fetch_cached_incident",
                        [("service", service)],
                        "aux1",
                        cached_res,
                        "Use the fallback note to recommend one focused first check.",
                        "note2",
                        response,
                    )
                )
        elif prompt.startswith("Differentiate"):
            user, expr, dres, chkres, response = item
            traces.append(
                g.multi_tool_trace(
                    "You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.",
                    math,
                    user,
                    ["Differentiate the expression.", "Verify the derivative by a second tool step.", "State the final derivative briefly."],
                    "Use one differentiation step, one verification step, then stop.",
                    "solve_symbolic",
                    [("expression", expr), ("operation", "differentiate"), ("variable", "x")],
                    "d1",
                    dres,
                    "The derivative result is already simple; verify it rather than adding another transform.",
                    "note1",
                    "derivative_check",
                    [("candidate_antiderivative", expr), ("target_expression", dres.removeprefix("Computed derivative: ")), ("variable", "x")],
                    "chk1",
                    chkres,
                    "The verification matches, so the final answer can just state the derivative cleanly.",
                    "note2",
                    response,
                )
            )
        else:
            user, expr, intres, chkres, _bad, response = item
            traces.append(
                g.multi_tool_trace(
                    "You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.",
                    math,
                    user,
                    ["Compute an antiderivative.", "Verify it by differentiation.", "State the final answer briefly."],
                    "Use one symbolic solve step, one derivative check, then stop.",
                    "solve_symbolic",
                    [("expression", expr), ("operation", "integrate"), ("variable", "x")],
                    "int1",
                    intres,
                    "The antiderivative is already simple; verify it directly rather than adding extra transforms.",
                    "note1",
                    "derivative_check",
                    [("candidate_antiderivative", "4*x^2 + ln(x)"), ("target_expression", expr), ("variable", "x")],
                    "chk1",
                    chkres,
                    "The derivative check confirms correctness, so the final answer can stay short.",
                    "note2",
                    response,
                )
            )

    final_rust_fillers = [
        ("Why is `Arc<[T]>` useful after building a collection once?", "Explain the main ownership tradeoff briefly.", "Tie it to sharing finalized read-only data.", "Keep it focused on freezing a collection after construction.", "Arc<[T]> is useful when you want to build data mutably once and then share it cheaply as immutable read-only slice data across tasks without cloning the elements again.", "note_arc_slice"),
        ("Why can `Box<[T]>` be a better final representation than `Vec<T>` in some APIs?", "Explain the representation tradeoff briefly.", "Tie it to fixed-size ownership after construction.", "Keep it focused on dropping unused capacity and signaling immutability of length.", "Box<[T]> can be a better final representation when the data is complete and will not grow anymore, because it owns exactly the finished slice without extra vector capacity and signals fixed-size intent.", "note_box_slice"),
        ("Why do Rust libraries sometimes expose newtypes around primitive IDs?", "Explain the type-safety reason briefly.", "Tie it to avoiding accidental mixups between logically different values.", "Keep it focused on stronger API boundaries.", "Newtypes around primitive IDs make APIs safer by preventing accidental mixing of logically different values that share the same underlying representation, such as user IDs versus order IDs.", "note_newtype"),
        ("Why is `Vec::into_boxed_slice` useful?", "Explain what it accomplishes briefly.", "Tie it to turning a growable buffer into a fixed-size owned slice.", "Keep it focused on finalizing storage.", "Vec::into_boxed_slice converts a growable vector into a fixed-size owned slice, which is useful when construction is done and you want a tighter final representation.", "note_into_boxed_slice"),
        ("Why is `Cow<'a, Path>` useful in path-rewriting code?", "Explain the main benefit briefly.", "Tie it to borrowed fast paths with owned rewritten outputs.", "Keep it short and centered on conditional allocation.", "Cow<'a, Path> is useful when many paths can be returned unchanged by borrowing, but some cases require constructing a rewritten owned path. It avoids allocation on the unchanged fast path.", "note_cow_path"),
        ("Why do people call `shrink_to_fit` sparingly on vectors?", "Explain the tradeoff briefly.", "Tie it to potential reallocation cost versus memory savings.", "Keep it focused on cost-benefit rather than blanket usage.", "People use `shrink_to_fit` sparingly because reducing spare capacity can cost a reallocation and may hurt if the vector soon grows again. It is most useful when you know the vector has reached a stable final size.", "note_shrink"),
        ("Why is `IndexMap` sometimes chosen over `HashMap`?", "Explain the main reason briefly.", "Tie it to preserving insertion order while still offering map semantics.", "Keep it short and practical.", "IndexMap is often chosen when you want map lookup behavior but also want iteration order to follow insertion order, which can simplify stable output or user-facing behavior.", "note_indexmap"),
        ("Why is `Arc<str>` preferable to cloning `String` into every task?", "Explain the main performance reason briefly.", "Tie it to shared immutable ownership.", "Keep the answer short and direct.", "Arc<str> is preferable when many tasks need the same immutable text because it avoids cloning full String buffers into each task and instead shares one allocation with cheap reference-counted clones.", "note_arcstr_reuse"),
        ("Why can a `Mutex` around a large shared cache become a bottleneck?", "Explain the concurrency reason briefly.", "Tie it to serialized access and contention.", "Keep it focused on lock contention, not implementation minutiae.", "A single Mutex can become a bottleneck because every cache access serializes through one lock, so concurrent readers and writers contend even when the underlying work is mostly independent. Sharding or read-optimized designs can reduce that contention.", "note_cache_mutex"),
    ]
    for user, todo, rationale, think, response, tag in final_rust_fillers:
        traces.append(
            g.no_tool_trace(
                "You are a Rust language assistant who gives compact conceptual explanations.",
                user,
                todo,
                rationale,
                think,
                response,
                tag,
            )
        )

    assert len(traces) == 300, len(traces)
    return traces


def main() -> int:
    traces = extend_records()
    bad: list[tuple[int, list[str]]] = []
    with OUT.open("w") as f:
        for i, trace in enumerate(traces, start=1):
            res = validate_trace(trace)
            if not res.valid:
                bad.append((i, res.errors))
            f.write(json.dumps({"trace": trace}, ensure_ascii=False) + "\n")
    rustish = sum(1 for t in traces if ("Rust" in t or "rust" in t or "cargo_" in t or "rustdoc_" in t))
    print(json.dumps({"count": len(traces), "rustish": rustish, "output": str(OUT), "invalid": bad}, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
