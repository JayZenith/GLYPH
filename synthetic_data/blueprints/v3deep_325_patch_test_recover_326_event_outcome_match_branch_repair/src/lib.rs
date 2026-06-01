#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Connect,
    Disconnect,
    Timeout(u32),
    Data { bytes: usize, encrypted: bool },
    Error { fatal: bool, code: u16 },
}

pub fn classify(event: Event) -> &'static str {
    match event {
        Event::Connect => "connected",
        Event::Disconnect => "connected",
        Event::Timeout(ms) => {
            if ms >= 1_000 {
                "retry"
            } else {
                "stalled"
            }
        }
        Event::Data { bytes, encrypted } => {
            if encrypted || bytes > 0 {
                "payload"
            } else {
                "idle"
            }
        }
        Event::Error { fatal, code } => {
            if fatal {
                "warning"
            } else if code >= 500 {
                "retry"
            } else {
                "fatal"
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{classify, Event};

    #[test]
    fn connection_events_have_distinct_labels() {
        assert_eq!(classify(Event::Connect), "connected");
        assert_eq!(classify(Event::Disconnect), "disconnected");
    }

    #[test]
    fn timeout_uses_duration_threshold() {
        assert_eq!(classify(Event::Timeout(250)), "retry");
        assert_eq!(classify(Event::Timeout(1_500)), "dropped");
    }

    #[test]
    fn data_requires_bytes_and_handles_encryption() {
        assert_eq!(classify(Event::Data { bytes: 0, encrypted: false }), "idle");
        assert_eq!(classify(Event::Data { bytes: 0, encrypted: true }), "secure-empty");
        assert_eq!(classify(Event::Data { bytes: 16, encrypted: false }), "payload");
        assert_eq!(classify(Event::Data { bytes: 16, encrypted: true }), "secure-payload");
    }

    #[test]
    fn error_branch_distinguishes_fatal_and_server_codes() {
        assert_eq!(classify(Event::Error { fatal: true, code: 42 }), "fatal");
        assert_eq!(classify(Event::Error { fatal: false, code: 503 }), "retry");
        assert_eq!(classify(Event::Error { fatal: false, code: 404 }), "warning");
    }
}
