#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
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

pub fn apply_event(status: Status, event: Event) -> Status {
    match (status, event) {
        (Status::Open, Event::Start) => Status::Open,
        (Status::InProgress, Event::Resolve) => Status::Closed,
        (Status::Resolved, Event::Close) => Status::Closed,
        (Status::Closed, Event::Reopen) => Status::InProgress,
        (s, _) => s,
    }
}

#[cfg(test)]
mod tests {
    use super::{apply_event, Event, Status};

    #[test]
    fn normal_flow_reaches_closed() {
        let s1 = apply_event(Status::Open, Event::Start);
        let s2 = apply_event(s1, Event::Resolve);
        let s3 = apply_event(s2, Event::Close);
        assert_eq!(s3, Status::Closed);
    }

    #[test]
    fn reopening_closed_ticket_goes_back_to_open() {
        assert_eq!(apply_event(Status::Closed, Event::Reopen), Status::Open);
    }

    #[test]
    fn invalid_close_from_open_leaves_state_unchanged() {
        assert_eq!(apply_event(Status::Open, Event::Close), Status::Open);
    }

    #[test]
    fn resolving_then_reopening_allows_work_to_restart() {
        let resolved = apply_event(Status::InProgress, Event::Resolve);
        assert_eq!(resolved, Status::Resolved);
        assert_eq!(apply_event(resolved, Event::Reopen), Status::Open);
    }
}
