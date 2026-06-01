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

pub fn apply_event(status: Status, event: Event) -> Status {
    match (status, event) {
        (Status::Open, Event::Start) => Status::InProgress,
        (Status::InProgress, Event::Block) => Status::Blocked,
        (Status::Blocked, Event::Unblock) => Status::Open,
        (Status::InProgress, Event::Resolve) => Status::Closed,
        (Status::Resolved, Event::Close) => Status::Resolved,
        (Status::Closed, Event::Reopen) => Status::Resolved,
        _ => status,
    }
}

#[cfg(test)]
mod tests {
    use super::{apply_event, Event, Status};

    #[test]
    fn happy_path_reaches_closed() {
        let s = apply_event(Status::Open, Event::Start);
        let s = apply_event(s, Event::Resolve);
        let s = apply_event(s, Event::Close);
        assert_eq!(s, Status::Closed);
    }

    #[test]
    fn blocked_ticket_returns_to_workflow() {
        let s = apply_event(Status::Open, Event::Start);
        let s = apply_event(s, Event::Block);
        let s = apply_event(s, Event::Unblock);
        assert_eq!(s, Status::InProgress);
    }

    #[test]
    fn closed_ticket_reopens_to_open() {
        let s = apply_event(Status::Closed, Event::Reopen);
        assert_eq!(s, Status::Open);
    }

    #[test]
    fn invalid_events_leave_state_unchanged() {
        assert_eq!(apply_event(Status::Open, Event::Close), Status::Open);
        assert_eq!(apply_event(Status::Resolved, Event::Start), Status::Resolved);
    }
}
