#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TicketState {
    Open,
    InProgress,
    Resolved,
    Closed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Start,
    Resolve,
    Close,
    Reopen,
}

pub fn apply_event(state: TicketState, event: Event) -> TicketState {
    match (state, event) {
        (TicketState::Open, Event::Start) => TicketState::InProgress,
        (TicketState::Open, Event::Resolve) => TicketState::Resolved,
        (TicketState::InProgress, Event::Close) => TicketState::Closed,
        (TicketState::Resolved, Event::Reopen) => TicketState::Open,
        (TicketState::Closed, Event::Reopen) => TicketState::InProgress,
        _ => state,
    }
}

pub fn apply_events(mut state: TicketState, events: &[Event]) -> TicketState {
    for &event in events {
        state = apply_event(state, event);
    }
    state
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_moves_open_ticket_to_in_progress() {
        assert_eq!(apply_event(TicketState::Open, Event::Start), TicketState::InProgress);
    }

    #[test]
    fn resolve_moves_in_progress_ticket_to_resolved() {
        assert_eq!(apply_event(TicketState::InProgress, Event::Resolve), TicketState::Resolved);
    }

    #[test]
    fn close_only_works_after_resolution() {
        assert_eq!(apply_event(TicketState::Resolved, Event::Close), TicketState::Closed);
        assert_eq!(apply_event(TicketState::InProgress, Event::Close), TicketState::InProgress);
    }

    #[test]
    fn reopen_from_resolved_returns_to_in_progress() {
        assert_eq!(apply_event(TicketState::Resolved, Event::Reopen), TicketState::InProgress);
    }

    #[test]
    fn reopen_from_closed_returns_to_open() {
        assert_eq!(apply_event(TicketState::Closed, Event::Reopen), TicketState::Open);
    }

    #[test]
    fn workflow_sequence_respects_all_transitions() {
        let events = [Event::Start, Event::Resolve, Event::Close, Event::Reopen];
        assert_eq!(apply_events(TicketState::Open, &events), TicketState::Open);
    }
}
