#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Connect { secure: bool },
    Message { urgent: bool, len: usize },
    Disconnect { error: Option<u16> },
    Tick,
}

pub fn action_for(event: Event) -> &'static str {
    match event {
        Event::Connect { .. } => "connect:plain",
        Event::Message { .. } => "message:normal",
        Event::Disconnect { .. } => "disconnect:clean",
        Event::Tick => "idle",
    }
}

#[cfg(test)]
mod tests {
    use super::{action_for, Event};

    #[test]
    fn connect_secure_and_plain_are_distinct() {
        assert_eq!(action_for(Event::Connect { secure: true }), "connect:tls");
        assert_eq!(action_for(Event::Connect { secure: false }), "connect:plain");
    }

    #[test]
    fn message_urgent_overrides_length() {
        assert_eq!(action_for(Event::Message { urgent: true, len: 0 }), "message:urgent");
        assert_eq!(action_for(Event::Message { urgent: true, len: 500 }), "message:urgent");
    }

    #[test]
    fn message_length_buckets_non_urgent() {
        assert_eq!(action_for(Event::Message { urgent: false, len: 0 }), "message:empty");
        assert_eq!(action_for(Event::Message { urgent: false, len: 5 }), "message:short");
        assert_eq!(action_for(Event::Message { urgent: false, len: 120 }), "message:long");
    }

    #[test]
    fn disconnect_error_codes_have_branches() {
        assert_eq!(action_for(Event::Disconnect { error: None }), "disconnect:clean");
        assert_eq!(action_for(Event::Disconnect { error: Some(503) }), "disconnect:retry");
        assert_eq!(action_for(Event::Disconnect { error: Some(410) }), "disconnect:error");
    }

    #[test]
    fn tick_is_ping() {
        assert_eq!(action_for(Event::Tick), "tick:ping");
    }
}
