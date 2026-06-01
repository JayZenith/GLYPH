#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    New,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ticket {
    pub status: Status,
    pub assignee: Option<&'static str>,
    pub resolution: Option<&'static str>,
    pub closed: bool,
}

impl Ticket {
    pub fn new() -> Self {
        Self {
            status: Status::New,
            assignee: None,
            resolution: None,
            closed: false,
        }
    }

    pub fn assign(mut self, who: &'static str) -> Self {
        self.assignee = Some(who);
        self
    }

    pub fn apply(&mut self, event: Event) -> bool {
        match event {
            Event::Start => {
                if self.assignee.is_some() {
                    self.status = Status::InProgress;
                    true
                } else {
                    false
                }
            }
            Event::Block => {
                self.status = Status::Blocked;
                true
            }
            Event::Unblock => {
                self.status = Status::New;
                true
            }
            Event::Resolve => {
                self.status = Status::Resolved;
                true
            }
            Event::Close => {
                self.status = Status::Closed;
                self.closed = true;
                true
            }
            Event::Reopen => {
                self.status = Status::InProgress;
                true
            }
        }
    }
}

pub fn apply_events(ticket: &mut Ticket, events: &[Event]) -> usize {
    let mut applied = 0;
    for &event in events {
        if ticket.apply(event) {
            applied += 1;
        }
    }
    applied
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_requires_assignee_and_only_from_new() {
        let mut unassigned = Ticket::new();
        assert!(!unassigned.apply(Event::Start));
        assert_eq!(unassigned.status, Status::New);

        let mut assigned = Ticket::new().assign("dev");
        assert!(assigned.apply(Event::Start));
        assert_eq!(assigned.status, Status::InProgress);

        assert!(!assigned.apply(Event::Start));
        assert_eq!(assigned.status, Status::InProgress);
    }

    #[test]
    fn blocked_unblock_round_trip_restores_progress_not_new() {
        let mut t = Ticket::new().assign("dev");
        assert!(t.apply(Event::Start));
        assert!(t.apply(Event::Block));
        assert_eq!(t.status, Status::Blocked);
        assert!(t.apply(Event::Unblock));
        assert_eq!(t.status, Status::InProgress);
    }

    #[test]
    fn resolve_requires_in_progress_and_sets_resolution() {
        let mut fresh = Ticket::new().assign("dev");
        assert!(!fresh.apply(Event::Resolve));
        assert_eq!(fresh.status, Status::New);
        assert_eq!(fresh.resolution, None);

        let mut active = Ticket::new().assign("dev");
        assert!(active.apply(Event::Start));
        assert!(active.apply(Event::Resolve));
        assert_eq!(active.status, Status::Resolved);
        assert_eq!(active.resolution, Some("done"));
    }

    #[test]
    fn close_requires_resolved_and_reopen_clears_terminal_fields() {
        let mut t = Ticket::new().assign("dev");
        assert!(t.apply(Event::Start));
        assert!(!t.apply(Event::Close));
        assert_eq!(t.status, Status::InProgress);
        assert!(!t.closed);

        assert!(t.apply(Event::Resolve));
        assert!(t.apply(Event::Close));
        assert_eq!(t.status, Status::Closed);
        assert!(t.closed);
        assert_eq!(t.resolution, Some("done"));

        assert!(t.apply(Event::Reopen));
        assert_eq!(t.status, Status::InProgress);
        assert!(!t.closed);
        assert_eq!(t.resolution, None);
    }

    #[test]
    fn apply_events_counts_only_valid_transitions() {
        let mut t = Ticket::new().assign("dev");
        let applied = apply_events(
            &mut t,
            &[
                Event::Resolve,
                Event::Start,
                Event::Block,
                Event::Unblock,
                Event::Resolve,
                Event::Close,
                Event::Reopen,
            ],
        );
        assert_eq!(applied, 6);
        assert_eq!(t.status, Status::InProgress);
        assert!(!t.closed);
        assert_eq!(t.resolution, None);
    }
}
