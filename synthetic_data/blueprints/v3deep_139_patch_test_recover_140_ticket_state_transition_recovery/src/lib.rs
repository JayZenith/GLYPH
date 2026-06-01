#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TicketState {
    New,
    InProgress,
    Resolved,
    Closed,
}

pub fn apply_event(state: TicketState, event: &str) -> TicketState {
    match event {
        "start" => TicketState::InProgress,
        "resolve" => TicketState::Resolved,
        "close" => TicketState::Closed,
        "reopen" => TicketState::New,
        _ => state,
    }
}

#[cfg(test)]
mod tests {
    use super::{apply_event, TicketState};

    #[test]
    fn start_only_moves_new_ticket() {
        assert_eq!(apply_event(TicketState::New, "start"), TicketState::InProgress);
        assert_eq!(apply_event(TicketState::Resolved, "start"), TicketState::Resolved);
        assert_eq!(apply_event(TicketState::Closed, "start"), TicketState::Closed);
    }

    #[test]
    fn close_requires_resolved_state() {
        assert_eq!(apply_event(TicketState::Resolved, "close"), TicketState::Closed);
        assert_eq!(apply_event(TicketState::InProgress, "close"), TicketState::InProgress);
        assert_eq!(apply_event(TicketState::New, "close"), TicketState::New);
    }

    #[test]
    fn reopen_returns_closed_or_resolved_to_in_progress() {
        assert_eq!(apply_event(TicketState::Closed, "reopen"), TicketState::InProgress);
        assert_eq!(apply_event(TicketState::Resolved, "reopen"), TicketState::InProgress);
        assert_eq!(apply_event(TicketState::New, "reopen"), TicketState::New);
    }

    #[test]
    fn resolve_only_advances_in_progress() {
        assert_eq!(apply_event(TicketState::InProgress, "resolve"), TicketState::Resolved);
        assert_eq!(apply_event(TicketState::New, "resolve"), TicketState::New);
        assert_eq!(apply_event(TicketState::Closed, "resolve"), TicketState::Closed);
    }
}
