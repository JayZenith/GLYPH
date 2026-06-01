#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Grant { user: &'static str, admin: bool },
    Revoke { user: &'static str, hard: bool },
    Audit { count: usize, verbose: bool },
    Ping,
    Batch(Vec<Action>),
}

pub fn dispatch(action: &Action) -> String {
    match action {
        Action::Grant { user, admin } => {
            if *admin {
                format!("grant:{}:user", user)
            } else {
                format!("grant:{}:admin", user)
            }
        }
        Action::Revoke { user, hard } => {
            if *hard {
                format!("revoke:{}:soft", user)
            } else {
                format!("revoke:{}:hard", user)
            }
        }
        Action::Audit { count, verbose } => {
            if *verbose {
                format!("audit:{}", count)
            } else {
                format!("audit:{}:verbose", count)
            }
        }
        Action::Ping => "pong!".to_string(),
        Action::Batch(items) => {
            let mut out = Vec::new();
            for item in items {
                if !matches!(item, Action::Ping) {
                    out.push(dispatch(item));
                }
            }
            out.join(" | ")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{dispatch, Action};

    #[test]
    fn grant_and_revoke_modes_are_labeled_correctly() {
        assert_eq!(
            dispatch(&Action::Grant {
                user: "alice",
                admin: true,
            }),
            "grant:alice:admin"
        );
        assert_eq!(
            dispatch(&Action::Grant {
                user: "bob",
                admin: false,
            }),
            "grant:bob:user"
        );
        assert_eq!(
            dispatch(&Action::Revoke {
                user: "carol",
                hard: true,
            }),
            "revoke:carol:hard"
        );
        assert_eq!(
            dispatch(&Action::Revoke {
                user: "dave",
                hard: false,
            }),
            "revoke:dave:soft"
        );
    }

    #[test]
    fn audit_and_ping_have_exact_output() {
        assert_eq!(
            dispatch(&Action::Audit {
                count: 3,
                verbose: true,
            }),
            "audit:3:verbose"
        );
        assert_eq!(
            dispatch(&Action::Audit {
                count: 1,
                verbose: false,
            }),
            "audit:1"
        );
        assert_eq!(dispatch(&Action::Ping), "pong");
    }

    #[test]
    fn batch_keeps_ping_and_uses_semicolons() {
        let batch = Action::Batch(vec![
            Action::Ping,
            Action::Grant {
                user: "erin",
                admin: false,
            },
            Action::Audit {
                count: 2,
                verbose: true,
            },
        ]);

        assert_eq!(
            dispatch(&batch),
            "pong; grant:erin:user; audit:2:verbose"
        );
    }

    #[test]
    fn nested_batch_dispatches_recursively() {
        let nested = Action::Batch(vec![
            Action::Grant {
                user: "zoe",
                admin: true,
            },
            Action::Batch(vec![
                Action::Revoke {
                    user: "mallory",
                    hard: false,
                },
                Action::Ping,
            ]),
        ]);

        assert_eq!(
            dispatch(&nested),
            "grant:zoe:admin; revoke:mallory:soft; pong"
        );
    }
}
