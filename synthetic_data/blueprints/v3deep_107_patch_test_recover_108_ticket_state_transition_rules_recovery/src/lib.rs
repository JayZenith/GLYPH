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
    Close,
    Reopen,
}

pub fn apply_event(status: Status, event: Event) -> Status {
    match (status, event) {
        (Status::Open, Event::Start) => Status::InProgress,
        (Status::InProgress, Event::Block) => Status::Blocked,
        (Status::Blocked, Event::Unblock) => Status::Open,
        (Status::InProgress, Event::Resolve) => Status::Closed,
        (Status::Resolved, Event::Close) => Status::Resolved,
        (Status::Closed, Event::Reopen) => Status::InProgress,
        (s, _) => s,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn main_path_reaches_closed() {
        let mut s = Status::Open;
        s = apply_event(s, Event::Start);
        s = apply_event(s, Event::Resolve);
        s = apply_event(s, Event::Close);
        assert_eq!(s, Status::Closed);
    }

    #[test]
    fn blocked_ticket_returns_to_work() {
        let mut s = Status::Open;
        s = apply_event(s, Event::Start);
        s = apply_event(s, Event::Block);
        s = apply_event(s, Event::Unblock);
        assert_eq!(s, Status::InProgress);
    }

    #[test]
    fn only_closed_ticket_can_reopen() {
        assert_eq!(apply_event(Status::Resolved, Event::Reopen), Status::Resolved);
        assert_eq!(apply_event(Status::Closed, Event::Reopen), Status::Open);
    }

    #[test]
    fn closing_requires_resolved_state() {
        assert_eq!(apply_event(Status::InProgress, Event::Close), Status::InProgress);
        assert_eq!(apply_event(Status::Resolved, Event::Close), Status::Closed);
    }
}
