#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    New,
    InProgress,
    Blocked,
    Resolved,
    Closed,
    Reopened,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ticket {
    pub state: State,
    pub unresolved_blocks: u32,
    pub resolution_count: u32,
    pub close_count: u32,
}

impl Ticket {
    pub fn new() -> Self {
        Self {
            state: State::New,
            unresolved_blocks: 0,
            resolution_count: 0,
            close_count: 0,
        }
    }

    pub fn apply(&mut self, event: Event) {
        match event {
            Event::Start => {
                if self.state == State::New {
                    self.state = State::InProgress;
                }
            }
            Event::Block => {
                self.unresolved_blocks += 1;
                self.state = State::Blocked;
            }
            Event::Unblock => {
                if self.unresolved_blocks > 0 {
                    self.unresolved_blocks -= 1;
                }
                self.state = State::InProgress;
            }
            Event::Resolve => {
                self.resolution_count += 1;
                self.state = State::Resolved;
            }
            Event::Close => {
                self.close_count += 1;
                self.state = State::Closed;
            }
            Event::Reopen => {
                self.state = State::Reopened;
            }
        }
    }
}

pub fn run(events: &[Event]) -> Ticket {
    let mut ticket = Ticket::new();
    for &event in events {
        ticket.apply(event);
    }
    ticket
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn block_then_unblock_returns_to_in_progress_only_after_last_block_is_cleared() {
        let ticket = run(&[
            Event::Start,
            Event::Block,
            Event::Block,
            Event::Unblock,
        ]);
        assert_eq!(ticket.unresolved_blocks, 1);
        assert_eq!(ticket.state, State::Blocked);
    }

    #[test]
    fn close_requires_resolved_state() {
        let ticket = run(&[Event::Start, Event::Close]);
        assert_eq!(ticket.close_count, 0);
        assert_eq!(ticket.state, State::InProgress);
    }

    #[test]
    fn resolve_is_ignored_while_blocked() {
        let ticket = run(&[Event::Start, Event::Block, Event::Resolve]);
        assert_eq!(ticket.resolution_count, 0);
        assert_eq!(ticket.state, State::Blocked);
    }

    #[test]
    fn reopen_from_closed_returns_to_in_progress_without_losing_history() {
        let ticket = run(&[
            Event::Start,
            Event::Resolve,
            Event::Close,
            Event::Reopen,
        ]);
        assert_eq!(ticket.state, State::InProgress);
        assert_eq!(ticket.resolution_count, 1);
        assert_eq!(ticket.close_count, 1);
    }

    #[test]
    fn new_ticket_cannot_be_blocked_until_started() {
        let ticket = run(&[Event::Block]);
        assert_eq!(ticket.unresolved_blocks, 0);
        assert_eq!(ticket.state, State::New);
    }
}
