#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
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

pub fn transition(state: State, event: Event) -> State {
    match (state, event) {
        (State::Open, Event::Start) => State::InProgress,
        (State::Open, Event::Close) => State::Closed,
        (State::InProgress, Event::Block) => State::Blocked,
        (State::Blocked, Event::Unblock) => State::Open,
        (State::InProgress, Event::Resolve) => State::Closed,
        (State::Blocked, Event::Resolve) => State::Resolved,
        (State::Resolved, Event::Close) => State::Resolved,
        (State::Resolved, Event::Reopen) => State::Open,
        (State::Closed, Event::Reopen) => State::Resolved,
        _ => state,
    }
}

#[cfg(test)]
mod tests {
    use super::{transition, Event, State};

    #[test]
    fn expected_ticket_flow_transitions() {
        assert_eq!(transition(State::Open, Event::Start), State::InProgress);
        assert_eq!(transition(State::InProgress, Event::Block), State::Blocked);
        assert_eq!(transition(State::Blocked, Event::Unblock), State::InProgress);
        assert_eq!(transition(State::InProgress, Event::Resolve), State::Resolved);
        assert_eq!(transition(State::Resolved, Event::Close), State::Closed);
    }

    #[test]
    fn reopen_returns_work_to_open_state() {
        assert_eq!(transition(State::Resolved, Event::Reopen), State::Open);
        assert_eq!(transition(State::Closed, Event::Reopen), State::Open);
    }

    #[test]
    fn invalid_events_leave_state_unchanged() {
        assert_eq!(transition(State::Open, Event::Unblock), State::Open);
        assert_eq!(transition(State::Closed, Event::Resolve), State::Closed);
    }
}
