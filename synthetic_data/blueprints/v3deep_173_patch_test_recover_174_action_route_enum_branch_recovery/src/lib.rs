#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    View,
    Edit { dirty: bool },
    Delete { hard: bool, confirmed: bool },
    Share(Option<String>),
    Archive { age_days: u32, pinned: bool },
    Sync { online: bool, pending: u32 },
}

pub fn route(action: Action) -> &'static str {
    match action {
        Action::View => "display",
        Action::Edit { dirty } => {
            if dirty { "edit" } else { "display" }
        }
        Action::Delete { hard, confirmed } => {
            if hard { "delete_now" } else if confirmed { "trash" } else { "blocked" }
        }
        Action::Share(target) => match target {
            Some(_) => "share_link",
            None => "noop",
        },
        Action::Archive { age_days, pinned } => {
            if pinned { "archive" } else if age_days > 30 { "archive" } else { "keep" }
        }
        Action::Sync { online, pending } => {
            if online && pending > 0 { "sync_now" } else if online { "synced" } else { "offline" }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{route, Action};

    #[test]
    fn view_and_edit_routes() {
        assert_eq!(route(Action::View), "display");
        assert_eq!(route(Action::Edit { dirty: true }), "edit");
        assert_eq!(route(Action::Edit { dirty: false }), "edit_preview");
    }

    #[test]
    fn delete_routes_require_confirmation() {
        assert_eq!(route(Action::Delete { hard: false, confirmed: false }), "blocked");
        assert_eq!(route(Action::Delete { hard: false, confirmed: true }), "trash");
        assert_eq!(route(Action::Delete { hard: true, confirmed: false }), "blocked");
        assert_eq!(route(Action::Delete { hard: true, confirmed: true }), "delete_now");
    }

    #[test]
    fn share_routes_distinguish_targets() {
        assert_eq!(route(Action::Share(None)), "share_picker");
        assert_eq!(route(Action::Share(Some(String::new()))), "share_picker");
        assert_eq!(route(Action::Share(Some("team".into()))), "share_link");
    }

    #[test]
    fn archive_routes_respect_pin_and_age() {
        assert_eq!(route(Action::Archive { age_days: 45, pinned: false }), "archive");
        assert_eq!(route(Action::Archive { age_days: 45, pinned: true }), "pinned_keep");
        assert_eq!(route(Action::Archive { age_days: 5, pinned: false }), "keep");
    }

    #[test]
    fn sync_routes_handle_pending_and_offline() {
        assert_eq!(route(Action::Sync { online: true, pending: 3 }), "sync_now");
        assert_eq!(route(Action::Sync { online: true, pending: 0 }), "idle");
        assert_eq!(route(Action::Sync { online: false, pending: 0 }), "offline");
        assert_eq!(route(Action::Sync { online: false, pending: 4 }), "queue_sync");
    }
}
