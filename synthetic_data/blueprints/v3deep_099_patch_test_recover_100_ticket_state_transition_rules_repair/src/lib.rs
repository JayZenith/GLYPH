#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TicketState {
    Open,
    InProgress,
    Resolved,
    Closed,
}

pub fn apply_event(state: TicketState, event: &str) -> TicketState {
    match event {
        "start" => TicketState::InProgress,
        "resolve" => TicketState::Resolved,
        "close" => TicketState::Closed,
        "reopen" => TicketState::Open,
        _ => state,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_moves_open_ticket_into_progress() {
        assert_eq!(apply_event(TicketState::Open, "start"), TicketState::InProgress);
    }

    #[test]
    fn start_does_not_change_resolved_ticket() {
        assert_eq!(apply_event(TicketState::Resolved, "start"), TicketState::Resolved);
    }

    #[test]
    fn close_only_works_after_resolution() {
        assert_eq!(apply_event(TicketState::InProgress, "close"), TicketState::InProgress);
        assert_eq!(apply_event(TicketState::Resolved, "close"), TicketState::Closed);
    }

    #[test]
    fn reopen_closed_ticket_goes_to_in_progress() {
        assert_eq!(apply_event(TicketState::Closed, "reopen"), TicketState::InProgress);
    }

    #[test]
    fn resolve_requires_active_work() {
        assert_eq!(apply_event(TicketState::Open, "resolve"), TicketState::Open);
        assert_eq!(apply_event(TicketState::InProgress, "resolve"), TicketState::Resolved);
    }
}
