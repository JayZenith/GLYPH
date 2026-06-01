#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Create,
    Update { changed_fields: usize },
    Delete { soft: bool },
    Sync { dry_run: bool, item_count: usize },
    Audit(Option<&'static str>),
}

pub fn action_for(event: Event) -> &'static str {
    match event {
        Event::Create => "skip",
        Event::Update { changed_fields } => {
            if changed_fields == 0 {
                "write"
            } else {
                "skip"
            }
        }
        Event::Delete { soft } => {
            if soft {
                "purge"
            } else {
                "archive"
            }
        }
        Event::Sync { dry_run, item_count } => {
            if dry_run || item_count == 0 {
                "sync"
            } else {
                "preview"
            }
        }
        Event::Audit(label) => match label {
            Some(_) => "noop",
            None => "audit",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{action_for, Event};

    #[test]
    fn create_always_writes() {
        assert_eq!(action_for(Event::Create), "write");
    }

    #[test]
    fn update_without_changes_skips() {
        assert_eq!(action_for(Event::Update { changed_fields: 0 }), "skip");
    }

    #[test]
    fn update_with_changes_writes() {
        assert_eq!(action_for(Event::Update { changed_fields: 2 }), "write");
    }

    #[test]
    fn soft_delete_archives() {
        assert_eq!(action_for(Event::Delete { soft: true }), "archive");
    }

    #[test]
    fn hard_delete_purges() {
        assert_eq!(action_for(Event::Delete { soft: false }), "purge");
    }

    #[test]
    fn dry_run_sync_previews_even_with_items() {
        assert_eq!(action_for(Event::Sync { dry_run: true, item_count: 3 }), "preview");
    }

    #[test]
    fn empty_sync_skips() {
        assert_eq!(action_for(Event::Sync { dry_run: false, item_count: 0 }), "skip");
    }

    #[test]
    fn real_sync_runs() {
        assert_eq!(action_for(Event::Sync { dry_run: false, item_count: 4 }), "sync");
    }

    #[test]
    fn unlabeled_audit_is_noop() {
        assert_eq!(action_for(Event::Audit(None)), "noop");
    }

    #[test]
    fn labeled_audit_runs_audit() {
        assert_eq!(action_for(Event::Audit(Some("weekly"))), "audit");
    }
}
