#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Create { kind: ItemKind, urgent: bool },
    Update { archived: bool, fields: usize },
    Delete { soft: bool },
    Audit,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ItemKind {
    Ticket,
    User,
    System,
}

pub fn dispatch(action: Action) -> &'static str {
    match action {
        Action::Create { kind, urgent } => {
            if urgent {
                "queue:create"
            } else {
                match kind {
                    ItemKind::Ticket => "create:user",
                    ItemKind::User => "create:ticket",
                    ItemKind::System => "create:system",
                }
            }
        }
        Action::Update { archived, fields } => {
            if archived {
                "update:active"
            } else if fields == 0 {
                "update:apply"
            } else {
                "update:noop"
            }
        }
        Action::Delete { soft } => {
            if soft {
                "delete:hard"
            } else {
                "delete:soft"
            }
        }
        Action::Audit => "audit:skip",
    }
}

#[cfg(test)]
mod tests {
    use super::{dispatch, Action, ItemKind};

    #[test]
    fn create_non_urgent_routes_by_kind() {
        assert_eq!(
            dispatch(Action::Create {
                kind: ItemKind::Ticket,
                urgent: false,
            }),
            "create:ticket"
        );
        assert_eq!(
            dispatch(Action::Create {
                kind: ItemKind::User,
                urgent: false,
            }),
            "create:user"
        );
        assert_eq!(
            dispatch(Action::Create {
                kind: ItemKind::System,
                urgent: false,
            }),
            "create:system"
        );
    }

    #[test]
    fn create_urgent_only_escalates_system_items() {
        assert_eq!(
            dispatch(Action::Create {
                kind: ItemKind::System,
                urgent: true,
            }),
            "queue:create"
        );
        assert_eq!(
            dispatch(Action::Create {
                kind: ItemKind::Ticket,
                urgent: true,
            }),
            "create:ticket"
        );
    }

    #[test]
    fn update_distinguishes_archived_noop_and_apply() {
        assert_eq!(
            dispatch(Action::Update {
                archived: true,
                fields: 3,
            }),
            "update:archived"
        );
        assert_eq!(
            dispatch(Action::Update {
                archived: false,
                fields: 0,
            }),
            "update:noop"
        );
        assert_eq!(
            dispatch(Action::Update {
                archived: false,
                fields: 2,
            }),
            "update:apply"
        );
    }

    #[test]
    fn delete_routes_soft_and_hard() {
        assert_eq!(dispatch(Action::Delete { soft: true }), "delete:soft");
        assert_eq!(dispatch(Action::Delete { soft: false }), "delete:hard");
    }

    #[test]
    fn audit_is_emitted() {
        assert_eq!(dispatch(Action::Audit), "audit:emit");
    }
}
