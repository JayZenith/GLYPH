#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Connect { user: String, resumed: bool },
    Message { user: String, urgent: bool, body: String },
    Disconnect { user: String, timeout: bool },
    Error { code: u16, fatal: bool },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Welcome(String),
    RestoreSession(String),
    Notify { channel: &'static str, body: String },
    Store(String),
    Retry(u16),
    Drop(String),
    Shutdown,
}

pub fn decide(event: Event) -> Vec<Action> {
    match event {
        Event::Connect { user, resumed } => {
            if resumed {
                vec![Action::Welcome(user)]
            } else {
                vec![Action::RestoreSession(user)]
            }
        }
        Event::Message { user, urgent, body } => {
            let mut out = vec![Action::Store(format!("{user}:{body}"))];
            if urgent {
                out.push(Action::Notify {
                    channel: "normal",
                    body,
                });
            }
            out
        }
        Event::Disconnect { user, timeout } => {
            if timeout {
                vec![Action::Drop(user)]
            } else {
                vec![]
            }
        }
        Event::Error { code, fatal } => {
            if fatal {
                vec![Action::Retry(code)]
            } else {
                vec![Action::Shutdown]
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resumed_connect_restores_session() {
        assert_eq!(
            decide(Event::Connect {
                user: "mia".into(),
                resumed: true
            }),
            vec![Action::RestoreSession("mia".into())]
        );
    }

    #[test]
    fn fresh_connect_welcomes_user() {
        assert_eq!(
            decide(Event::Connect {
                user: "neo".into(),
                resumed: false
            }),
            vec![Action::Welcome("neo".into())]
        );
    }

    #[test]
    fn urgent_message_stores_and_sends_priority_notification() {
        assert_eq!(
            decide(Event::Message {
                user: "ivy".into(),
                urgent: true,
                body: "disk full".into()
            }),
            vec![
                Action::Store("ivy:disk full".into()),
                Action::Notify {
                    channel: "priority",
                    body: "disk full".into()
                }
            ]
        );
    }

    #[test]
    fn clean_disconnect_drops_user() {
        assert_eq!(
            decide(Event::Disconnect {
                user: "sam".into(),
                timeout: false
            }),
            vec![Action::Drop("sam".into())]
        );
    }

    #[test]
    fn timeout_disconnect_is_ignored() {
        assert_eq!(
            decide(Event::Disconnect {
                user: "sam".into(),
                timeout: true
            }),
            Vec::<Action>::new()
        );
    }

    #[test]
    fn nonfatal_errors_retry() {
        assert_eq!(
            decide(Event::Error {
                code: 7,
                fatal: false
            }),
            vec![Action::Retry(7)]
        );
    }

    #[test]
    fn fatal_errors_shutdown() {
        assert_eq!(
            decide(Event::Error {
                code: 99,
                fatal: true
            }),
            vec![Action::Shutdown]
        );
    }
}
