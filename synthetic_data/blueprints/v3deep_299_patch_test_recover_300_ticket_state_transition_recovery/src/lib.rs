#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Open,
    InProgress,
    Blocked,
    Resolved,
    Closed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Start,
    Block,
    Unblock,
    Resolve,
    Reopen,
    Close,
}

pub fn apply_events(events: &[Event]) -> Status {
    let mut status = Status::Open;

    for event in events {
        status = match (*event, status) {
            (Event::Start, Status::Open) => Status::InProgress,
            (Event::Block, Status::InProgress) => Status::Blocked,
            (Event::Unblock, Status::Blocked) => Status::Open,
            (Event::Resolve, Status::InProgress) => Status::Resolved,
            (Event::Resolve, Status::Blocked) => Status::Resolved,
            (Event::Close, Status::Resolved) => Status::Closed,
            (Event::Reopen, Status::Closed) => Status::InProgress,
            (Event::Reopen, Status::Resolved) => Status::Open,
            _ => status,
        };
    }

    status
}

#[cfg(test)]
mod tests {
    use super::{apply_events, Event, Status};

    #[test]
    fn blocked_ticket_returns_to_in_progress_when_unblocked() {
        let events = [Event::Start, Event::Block, Event::Unblock];
        assert_eq!(apply_events(&events), Status::InProgress);
    }

    #[test]
    fn blocked_ticket_cannot_resolve_until_unblocked() {
        let events = [Event::Start, Event::Block, Event::Resolve, Event::Unblock];
        assert_eq!(apply_events(&events), Status::InProgress);
    }

    #[test]
    fn reopen_from_resolved_goes_to_in_progress() {
        let events = [Event::Start, Event::Resolve, Event::Reopen];
        assert_eq!(apply_events(&events), Status::InProgress);
    }

    #[test]
    fn close_requires_resolved_and_reopen_after_close_returns_open() {
        let events = [Event::Close, Event::Start, Event::Close, Event::Resolve, Event::Close, Event::Reopen];
        assert_eq!(apply_events(&events), Status::Open);
    }
}
