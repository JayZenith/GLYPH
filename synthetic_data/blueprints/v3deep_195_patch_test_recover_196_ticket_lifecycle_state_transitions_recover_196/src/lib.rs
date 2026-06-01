#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TicketState {
    Open,
    InProgress,
    Resolved,
    Closed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TicketEvent {
    Start,
    Resolve,
    Reopen,
    Close,
}

pub fn apply_event(state: TicketState, event: TicketEvent) -> TicketState {
    match (state, event) {
        (TicketState::Open, TicketEvent::Start) => TicketState::InProgress,
        (TicketState::InProgress, TicketEvent::Resolve) => TicketState::Closed,
        (TicketState::Resolved, TicketEvent::Close) => TicketState::Resolved,
        (TicketState::Closed, TicketEvent::Reopen) => TicketState::Open,
        (_, TicketEvent::Close) => TicketState::Closed,
        _ => state,
    }
}

pub fn apply_events(mut state: TicketState, events: &[TicketEvent]) -> TicketState {
    for event in events {
        state = apply_event(state, *event);
    }
    state
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_moves_open_to_in_progress() {
        assert_eq!(apply_event(TicketState::Open, TicketEvent::Start), TicketState::InProgress);
    }

    #[test]
    fn resolve_moves_in_progress_to_resolved() {
        assert_eq!(apply_event(TicketState::InProgress, TicketEvent::Resolve), TicketState::Resolved);
    }

    #[test]
    fn close_only_moves_resolved_to_closed() {
        assert_eq!(apply_event(TicketState::Resolved, TicketEvent::Close), TicketState::Closed);
        assert_eq!(apply_event(TicketState::Open, TicketEvent::Close), TicketState::Open);
        assert_eq!(apply_event(TicketState::InProgress, TicketEvent::Close), TicketState::InProgress);
    }

    #[test]
    fn reopen_from_closed_goes_to_in_progress() {
        assert_eq!(apply_event(TicketState::Closed, TicketEvent::Reopen), TicketState::InProgress);
    }

    #[test]
    fn event_sequence_respects_transition_rules() {
        let events = [
            TicketEvent::Start,
            TicketEvent::Resolve,
            TicketEvent::Close,
            TicketEvent::Reopen,
        ];
        assert_eq!(apply_events(TicketState::Open, &events), TicketState::InProgress);
    }
}
