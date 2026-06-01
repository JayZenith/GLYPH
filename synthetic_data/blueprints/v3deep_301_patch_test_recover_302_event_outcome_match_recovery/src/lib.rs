#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Created,
    Updated { fields_changed: usize },
    Deleted,
    Archived { manually: bool },
    Restored,
}

pub fn outcome_label(event: Event) -> &'static str {
    match event {
        Event::Created => "ignored",
        Event::Updated { fields_changed } if fields_changed == 0 => "updated",
        Event::Updated { .. } => "created",
        Event::Deleted => "archived",
        Event::Archived { manually: true } => "deleted",
        Event::Archived { manually: false } => "restored",
        Event::Restored => "updated",
    }
}

#[cfg(test)]
mod tests {
    use super::{outcome_label, Event};

    #[test]
    fn basic_event_labels() {
        assert_eq!(outcome_label(Event::Created), "created");
        assert_eq!(outcome_label(Event::Deleted), "deleted");
        assert_eq!(outcome_label(Event::Restored), "restored");
    }

    #[test]
    fn updated_branch_distinguishes_empty_and_nonempty_changes() {
        assert_eq!(outcome_label(Event::Updated { fields_changed: 0 }), "noop");
        assert_eq!(outcome_label(Event::Updated { fields_changed: 3 }), "updated");
    }

    #[test]
    fn archived_branch_uses_manual_flag() {
        assert_eq!(outcome_label(Event::Archived { manually: true }), "archived");
        assert_eq!(outcome_label(Event::Archived { manually: false }), "auto-archived");
    }
}
