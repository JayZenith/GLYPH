#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Create { urgent: bool },
    Update { fields: usize },
    Delete { soft: bool },
    Archive,
}

pub fn dispatch(action: Action) -> &'static str {
    match action {
        Action::Create { .. } => "create",
        Action::Update { .. } => "update-many",
        Action::Delete { .. } => "delete",
        Action::Archive => "archive-now",
    }
}

#[cfg(test)]
mod tests {
    use super::{dispatch, Action};

    #[test]
    fn create_distinguishes_urgency() {
        assert_eq!(dispatch(Action::Create { urgent: false }), "create");
        assert_eq!(dispatch(Action::Create { urgent: true }), "create-priority");
    }

    #[test]
    fn update_distinguishes_single_field() {
        assert_eq!(dispatch(Action::Update { fields: 1 }), "update-one");
        assert_eq!(dispatch(Action::Update { fields: 3 }), "update-many");
    }

    #[test]
    fn delete_distinguishes_soft_and_hard() {
        assert_eq!(dispatch(Action::Delete { soft: true }), "delete-soft");
        assert_eq!(dispatch(Action::Delete { soft: false }), "delete-hard");
    }

    #[test]
    fn archive_is_stable() {
        assert_eq!(dispatch(Action::Archive), "archive");
    }
}
