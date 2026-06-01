#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Create,
    Update,
    Delete,
    Archive,
}

pub fn dispatch(action: Action, urgent: bool, dry_run: bool) -> &'static str {
    match action {
        Action::Create => {
            if urgent {
                "queue:create"
            } else {
                "create"
            }
        }
        Action::Update => {
            if dry_run {
                "update"
            } else {
                "preview:update"
            }
        }
        Action::Delete => {
            if dry_run {
                "delete"
            } else if urgent {
                "queue:delete"
            } else {
                "delete:confirmed"
            }
        }
        Action::Archive => {
            if urgent {
                "archive"
            } else if dry_run {
                "preview:archive"
            } else {
                "queue:archive"
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{dispatch, Action};

    #[test]
    fn create_and_update_routes() {
        assert_eq!(dispatch(Action::Create, false, false), "create");
        assert_eq!(dispatch(Action::Create, true, false), "queue:create");
        assert_eq!(dispatch(Action::Update, false, true), "preview:update");
        assert_eq!(dispatch(Action::Update, false, false), "update");
    }

    #[test]
    fn delete_prefers_dry_run_over_urgent() {
        assert_eq!(dispatch(Action::Delete, false, false), "delete:confirmed");
        assert_eq!(dispatch(Action::Delete, true, false), "queue:delete");
        assert_eq!(dispatch(Action::Delete, false, true), "preview:delete");
        assert_eq!(dispatch(Action::Delete, true, true), "preview:delete");
    }

    #[test]
    fn archive_uses_preview_and_urgent_queue() {
        assert_eq!(dispatch(Action::Archive, false, false), "archive");
        assert_eq!(dispatch(Action::Archive, false, true), "preview:archive");
        assert_eq!(dispatch(Action::Archive, true, false), "queue:archive");
        assert_eq!(dispatch(Action::Archive, true, true), "preview:archive");
    }
}
