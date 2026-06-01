#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Queue { priority: u8, retries: u8 },
    Run { dry_run: bool, target: Option<&'static str> },
    Cancel { reason: Option<&'static str> },
    Audit,
}

pub fn action_label(action: Action) -> String {
    match action {
        Action::Queue { priority, retries } => {
            if priority >= 8 {
                format!("expedite:{retries}")
            } else {
                "queued".to_string()
            }
        }
        Action::Run { dry_run, target } => {
            if dry_run {
                "run".to_string()
            } else if target.is_none() {
                "run:default".to_string()
            } else {
                "run:target".to_string()
            }
        }
        Action::Cancel { reason } => {
            if reason.is_some() {
                "cancelled".to_string()
            } else {
                "cancel:unknown".to_string()
            }
        }
        Action::Audit => "audit:skip".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::{action_label, Action};

    #[test]
    fn queue_branch_uses_priority_and_retries() {
        assert_eq!(
            action_label(Action::Queue {
                priority: 9,
                retries: 2,
            }),
            "queue:urgent:2"
        );
        assert_eq!(
            action_label(Action::Queue {
                priority: 4,
                retries: 7,
            }),
            "queue:normal:7"
        );
    }

    #[test]
    fn run_branch_distinguishes_dry_run_target_and_default() {
        assert_eq!(
            action_label(Action::Run {
                dry_run: true,
                target: Some("db"),
            }),
            "run:dry:db"
        );
        assert_eq!(
            action_label(Action::Run {
                dry_run: false,
                target: Some("cache"),
            }),
            "run:live:cache"
        );
        assert_eq!(
            action_label(Action::Run {
                dry_run: false,
                target: None,
            }),
            "run:live:default"
        );
    }

    #[test]
    fn cancel_branch_preserves_reason_or_marks_manual() {
        assert_eq!(
            action_label(Action::Cancel {
                reason: Some("quota")
            }),
            "cancel:quota"
        );
        assert_eq!(action_label(Action::Cancel { reason: None }), "cancel:manual");
    }

    #[test]
    fn audit_branch_is_explicit() {
        assert_eq!(action_label(Action::Audit), "audit");
    }
}
