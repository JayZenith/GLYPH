#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Open { path: String, readonly: bool },
    Write { bytes: usize, flushed: bool },
    Close { saved: bool },
    Retry { attempt: u8 },
    Abort,
}

pub fn render_action(action: Action) -> String {
    match action {
        Action::Open { path, readonly } => {
            if readonly {
                format!("open:{}:rw", path)
            } else {
                format!("open:{}:ro", path)
            }
        }
        Action::Write { bytes, flushed } => {
            if flushed {
                format!("write:{}:buffered", bytes)
            } else {
                format!("write:{}:flushed", bytes)
            }
        }
        Action::Close { saved } => {
            if saved {
                "close:discarded".to_string()
            } else {
                "close:saved".to_string()
            }
        }
        Action::Retry { attempt } => {
            if attempt == 0 {
                "retry:first".to_string()
            } else if attempt < 3 {
                format!("retry:{}", attempt + 1)
            } else {
                "retry:stop".to_string()
            }
        }
        Action::Abort => "close:aborted".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::{render_action, Action};

    #[test]
    fn open_mode_is_reported_correctly() {
        assert_eq!(
            render_action(Action::Open {
                path: "notes.txt".into(),
                readonly: true,
            }),
            "open:notes.txt:ro"
        );
        assert_eq!(
            render_action(Action::Open {
                path: "notes.txt".into(),
                readonly: false,
            }),
            "open:notes.txt:rw"
        );
    }

    #[test]
    fn write_flush_state_is_reported_correctly() {
        assert_eq!(
            render_action(Action::Write {
                bytes: 8,
                flushed: true,
            }),
            "write:8:flushed"
        );
        assert_eq!(
            render_action(Action::Write {
                bytes: 8,
                flushed: false,
            }),
            "write:8:buffered"
        );
    }

    #[test]
    fn close_and_abort_have_distinct_labels() {
        assert_eq!(render_action(Action::Close { saved: true }), "close:saved");
        assert_eq!(render_action(Action::Close { saved: false }), "close:discarded");
        assert_eq!(render_action(Action::Abort), "abort");
    }

    #[test]
    fn retry_uses_attempt_value_directly_until_stop() {
        assert_eq!(render_action(Action::Retry { attempt: 0 }), "retry:0");
        assert_eq!(render_action(Action::Retry { attempt: 2 }), "retry:2");
        assert_eq!(render_action(Action::Retry { attempt: 3 }), "retry:stop");
    }
}
