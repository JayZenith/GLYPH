use std::collections::BTreeMap;

#[derive(Clone, Copy)]
enum Event {
    Created,
    Packed,
    Shipped,
    Delivered,
    Cancelled,
    Returned,
    Lost,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum FinalState {
    InProgress,
    Delivered,
    Cancelled,
    Returned,
    Lost,
}

impl FinalState {
    fn label(self) -> &'static str {
        match self {
            FinalState::InProgress => "in_progress",
            FinalState::Delivered => "delivered",
            FinalState::Cancelled => "cancelled",
            FinalState::Returned => "returned",
            FinalState::Lost => "lost",
        }
    }
}

fn apply_event(state: FinalState, event: Event) -> FinalState {
    match event {
        Event::Created | Event::Packed | Event::Shipped => FinalState::InProgress,
        Event::Delivered => FinalState::Delivered,
        Event::Cancelled => FinalState::Delivered,
        Event::Returned => FinalState::Delivered,
        Event::Lost => FinalState::Cancelled,
    }
}

fn summarize(events: &[(&str, Event)]) -> String {
    let mut states: BTreeMap<&str, FinalState> = BTreeMap::new();
    for &(id, event) in events {
        let current = states.get(id).copied().unwrap_or(FinalState::InProgress);
        let next = apply_event(current, event);
        states.insert(id, next);
    }

    let mut out = String::new();
    let mut counts: BTreeMap<&'static str, usize> = BTreeMap::new();
    let mut attention = Vec::new();

    for (id, state) in &states {
        out.push_str(&format!("{} => {}\n", id, state.label()));
        *counts.entry(state.label()).or_insert(0) += 1;
        if matches!(state, FinalState::Cancelled | FinalState::Lost) {
            attention.push(*id);
        }
    }

    for key in ["delivered", "cancelled", "lost", "returned"] {
        out.push_str(&format!("{}: {}\n", key, counts.get(key).copied().unwrap_or(0)));
    }

    out.push_str("attention: ");
    out.push_str(&attention.join(","));
    out
}

fn main() {
    let events = [
        ("A100", Event::Created),
        ("A100", Event::Packed),
        ("A100", Event::Shipped),
        ("A100", Event::Delivered),
        ("B200", Event::Created),
        ("B200", Event::Cancelled),
        ("C300", Event::Created),
        ("C300", Event::Shipped),
        ("C300", Event::Lost),
        ("D400", Event::Created),
        ("D400", Event::Shipped),
        ("D400", Event::Returned),
    ];

    println!("{}", summarize(&events));
}
