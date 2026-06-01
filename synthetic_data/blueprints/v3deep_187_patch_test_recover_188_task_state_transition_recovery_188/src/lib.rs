#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Todo,
    InProgress,
    Blocked,
    Done,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Start,
    Block,
    Resume,
    Complete,
    Reopen,
}

pub fn apply_event(status: Status, event: Event) -> Status {
    match event {
        Event::Start => Status::InProgress,
        Event::Block => Status::Blocked,
        Event::Resume => Status::Todo,
        Event::Complete => Status::Done,
        Event::Reopen => Status::Todo,
    }
}

#[cfg(test)]
mod tests {
    use super::{apply_event, Event, Status};

    #[test]
    fn valid_transitions_change_state() {
        assert_eq!(apply_event(Status::Todo, Event::Start), Status::InProgress);
        assert_eq!(apply_event(Status::InProgress, Event::Block), Status::Blocked);
        assert_eq!(apply_event(Status::Blocked, Event::Resume), Status::InProgress);
        assert_eq!(apply_event(Status::InProgress, Event::Complete), Status::Done);
        assert_eq!(apply_event(Status::Done, Event::Reopen), Status::Todo);
    }

    #[test]
    fn invalid_transitions_leave_state_unchanged() {
        assert_eq!(apply_event(Status::Todo, Event::Block), Status::Todo);
        assert_eq!(apply_event(Status::Todo, Event::Complete), Status::Todo);
        assert_eq!(apply_event(Status::Blocked, Event::Start), Status::Blocked);
        assert_eq!(apply_event(Status::Done, Event::Complete), Status::Done);
    }

    #[test]
    fn done_items_only_reopen_to_todo() {
        assert_eq!(apply_event(Status::Done, Event::Start), Status::Done);
        assert_eq!(apply_event(Status::Done, Event::Resume), Status::Done);
        assert_eq!(apply_event(Status::Done, Event::Block), Status::Done);
        assert_eq!(apply_event(Status::Done, Event::Reopen), Status::Todo);
    }
}
