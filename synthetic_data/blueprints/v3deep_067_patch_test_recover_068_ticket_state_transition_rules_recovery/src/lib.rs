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
    match event {
        Event::Start => Status::InProgress,
        Event::Resolve => Status::Resolved,
        Event::Close => Status::Closed,
        Event::Reopen => Status::Open,
    }
}

pub fn apply_events(mut status: Status, events: &[Event]) -> Status {
    for &event in events {
        status = apply_event(status, event);
    }
    status
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_only_changes_open_ticket() {
        assert_eq!(apply_event(Status::Open, Event::Start), Status::InProgress);
        assert_eq!(apply_event(Status::Resolved, Event::Start), Status::Resolved);
    }

    #[test]
    fn resolve_only_changes_in_progress_ticket() {
        assert_eq!(apply_event(Status::InProgress, Event::Resolve), Status::Resolved);
        assert_eq!(apply_event(Status::Open, Event::Resolve), Status::Open);
    }

    #[test]
    fn close_only_changes_resolved_ticket() {
        assert_eq!(apply_event(Status::Resolved, Event::Close), Status::Closed);
        assert_eq!(apply_event(Status::InProgress, Event::Close), Status::InProgress);
    }

    #[test]
    fn reopen_only_changes_closed_ticket() {
        assert_eq!(apply_event(Status::Closed, Event::Reopen), Status::Open);
        assert_eq!(apply_event(Status::Resolved, Event::Reopen), Status::Resolved);
    }

    #[test]
    fn sequence_obeys_transition_rules() {
        let events = [Event::Start, Event::Resolve, Event::Close, Event::Reopen];
        assert_eq!(apply_events(Status::Open, &events), Status::Open);
    }
}
