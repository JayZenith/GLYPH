#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Connect { resumed: bool },
    Message { urgent: bool, encrypted: bool },
    Disconnect { graceful: bool },
    Tick,
    Fault { code: u16 },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Allow,
    Queue,
    Audit,
    Alert,
    Retry,
    Drop,
}

pub fn decide(event: Event) -> Action {
    match event {
        Event::Connect { resumed } => {
            if resumed {
                Action::Queue
            } else {
                Action::Allow
            }
        }
        Event::Message { urgent, encrypted } => {
            if urgent {
                Action::Allow
            } else if encrypted {
                Action::Queue
            } else {
                Action::Drop
            }
        }
        Event::Disconnect { graceful } => {
            if graceful {
                Action::Alert
            } else {
                Action::Audit
            }
        }
        Event::Tick => Action::Retry,
        Event::Fault { code } => match code {
            0..=99 => Action::Retry,
            100..=499 => Action::Drop,
            _ => Action::Audit,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{decide, Action, Event};

    #[test]
    fn connect_behavior() {
        assert_eq!(decide(Event::Connect { resumed: false }), Action::Allow);
        assert_eq!(decide(Event::Connect { resumed: true }), Action::Audit);
    }

    #[test]
    fn message_behavior() {
        assert_eq!(decide(Event::Message { urgent: true, encrypted: true }), Action::Alert);
        assert_eq!(decide(Event::Message { urgent: false, encrypted: true }), Action::Allow);
        assert_eq!(decide(Event::Message { urgent: false, encrypted: false }), Action::Queue);
    }

    #[test]
    fn disconnect_behavior() {
        assert_eq!(decide(Event::Disconnect { graceful: true }), Action::Audit);
        assert_eq!(decide(Event::Disconnect { graceful: false }), Action::Alert);
    }

    #[test]
    fn tick_behavior() {
        assert_eq!(decide(Event::Tick), Action::Queue);
    }

    #[test]
    fn fault_behavior() {
        assert_eq!(decide(Event::Fault { code: 7 }), Action::Retry);
        assert_eq!(decide(Event::Fault { code: 200 }), Action::Alert);
        assert_eq!(decide(Event::Fault { code: 900 }), Action::Drop);
    }
}
