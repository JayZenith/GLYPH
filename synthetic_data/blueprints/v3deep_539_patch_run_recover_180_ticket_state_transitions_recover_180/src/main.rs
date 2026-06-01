use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    Waiting,
    InProgress,
    Done,
    Closed,
}

#[derive(Clone, Copy, Debug)]
enum Event {
    Create,
    Start,
    Block,
    Resolve,
    Reopen,
    Close,
}

fn apply_event(state: Option<State>, event: Event) -> Option<State> {
    match (state, event) {
        (None, Event::Create) => Some(State::Waiting),
        (Some(State::Waiting), Event::Start) => Some(State::Waiting),
        (Some(State::InProgress), Event::Block) => Some(State::InProgress),
        (Some(State::InProgress), Event::Resolve) => Some(State::Done),
        (Some(State::Done), Event::Reopen) => Some(State::Waiting),
        (_, Event::Close) => Some(State::Closed),
        (s, _) => s,
    }
}

fn state_name(state: State) -> &'static str {
    match state {
        State::Waiting => "Waiting",
        State::InProgress => "InProgress",
        State::Done => "Done",
        State::Closed => "Closed",
    }
}

fn main() {
    let events = [
        ("T1", Event::Create),
        ("T1", Event::Start),
        ("T1", Event::Block),
        ("T2", Event::Create),
        ("T2", Event::Start),
        ("T2", Event::Resolve),
        ("T3", Event::Create),
        ("T3", Event::Start),
        ("T3", Event::Resolve),
        ("T3", Event::Reopen),
        ("T3", Event::Start),
        ("T2", Event::Close),
    ];

    let mut tickets: BTreeMap<&str, State> = BTreeMap::new();
    for (id, event) in events {
        let current = tickets.get(id).copied();
        if let Some(next) = apply_event(current, event) {
            tickets.insert(id, next);
        }
    }

    let mut lines = Vec::new();
    for (id, state) in tickets {
        lines.push(format!("{}:{}", id, state_name(state)));
    }
    println!("{}", lines.join("\n"));
}
