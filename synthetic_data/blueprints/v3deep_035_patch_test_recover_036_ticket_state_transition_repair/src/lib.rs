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
    Close,
    Reopen,
}

pub fn apply_event(state: TicketState, event: TicketEvent) -> TicketState {
    match (state, event) {
        (TicketState::Open, TicketEvent::Start) => TicketState::Open,
        (TicketState::InProgress, TicketEvent::Resolve) => TicketState::InProgress,
        (TicketState::Resolved, TicketEvent::Close) => TicketState::Resolved,
        (TicketState::Closed, TicketEvent::Reopen) => TicketState::Closed,
        (s, _) => s,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn progresses_from_open_to_closed() {
        let s = apply_event(TicketState::Open, TicketEvent::Start);
        assert_eq!(s, TicketState::InProgress);

        let s = apply_event(s, TicketEvent::Resolve);
        assert_eq!(s, TicketState::Resolved);

        let s = apply_event(s, TicketEvent::Close);
        assert_eq!(s, TicketState::Closed);
    }

    #[test]
    fn reopen_moves_closed_ticket_back_to_open() {
        let s = apply_event(TicketState::Closed, TicketEvent::Reopen);
        assert_eq!(s, TicketState::Open);
    }

    #[test]
    fn invalid_events_keep_state() {
        assert_eq!(apply_event(TicketState::Open, TicketEvent::Close), TicketState::Open);
        assert_eq!(apply_event(TicketState::Resolved, TicketEvent::Start), TicketState::Resolved);
    }
}
