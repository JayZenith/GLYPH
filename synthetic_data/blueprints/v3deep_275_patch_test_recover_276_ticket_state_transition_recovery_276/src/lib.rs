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
        status = match (status, event) {
            (Status::Open, Event::Start) => Status::InProgress,
            (Status::Open, Event::Close) => Status::Closed,
            (Status::InProgress, Event::Block) => Status::Blocked,
            (Status::Blocked, Event::Unblock) => Status::Open,
            (Status::InProgress, Event::Resolve) => Status::Closed,
            (Status::Blocked, Event::Resolve) => Status::Resolved,
            (Status::Resolved, Event::Close) => Status::Resolved,
            (Status::Resolved, Event::Reopen) => Status::Open,
            (Status::Closed, Event::Reopen) => Status::Resolved,
            _ => status,
        };
    }
    status
}

#[cfg(test)]
mod tests {
    use super::{apply_events, Event::*, Status::*};

    #[test]
    fn unresolved_close_from_open_is_allowed() {
        assert_eq!(apply_events(&[Close]), Closed);
    }

    #[test]
    fn unblock_returns_to_in_progress() {
        assert_eq!(apply_events(&[Start, Block, Unblock]), InProgress);
    }

    #[test]
    fn resolve_requires_explicit_close() {
        assert_eq!(apply_events(&[Start, Resolve]), Resolved);
    }

    #[test]
    fn resolved_can_then_close() {
        assert_eq!(apply_events(&[Start, Resolve, Close]), Closed);
    }

    #[test]
    fn reopen_from_resolved_goes_to_in_progress() {
        assert_eq!(apply_events(&[Start, Resolve, Reopen]), InProgress);
    }

    #[test]
    fn reopen_from_closed_goes_to_open() {
        assert_eq!(apply_events(&[Close, Reopen]), Open);
    }

    #[test]
    fn blocked_can_resolve_directly() {
        assert_eq!(apply_events(&[Start, Block, Resolve]), Resolved);
    }

    #[test]
    fn unknown_events_leave_state_unchanged() {
        assert_eq!(apply_events(&[Start, Start, Block, Block]), Blocked);
    }
}
