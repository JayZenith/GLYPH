#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Draft,
    Review,
    Approved,
    Rejected,
    Published,
    Archived,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Submit,
    Approve,
    Reject,
    Revise,
    Publish,
    Archive,
    Restore,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DocState {
    pub status: Status,
    pub review_rounds: u8,
    pub approved_at_least_once: bool,
    pub archive_count: u8,
}

impl DocState {
    pub fn new() -> Self {
        Self {
            status: Status::Draft,
            review_rounds: 0,
            approved_at_least_once: false,
            archive_count: 0,
        }
    }

    pub fn apply(&mut self, event: Event) {
        match event {
            Event::Submit => {
                self.status = Status::Review;
            }
            Event::Approve => {
                self.status = Status::Approved;
            }
            Event::Reject => {
                self.status = Status::Rejected;
            }
            Event::Revise => {
                self.status = Status::Draft;
            }
            Event::Publish => {
                self.status = Status::Published;
            }
            Event::Archive => {
                self.status = Status::Archived;
            }
            Event::Restore => {
                self.status = Status::Draft;
            }
        }
    }

    pub fn apply_all(events: &[Event]) -> Self {
        let mut state = Self::new();
        for event in events {
            state.apply(event.clone());
        }
        state
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn submit_only_from_draft_and_counts_review_rounds() {
        let state = DocState::apply_all(&[Event::Submit]);
        assert_eq!(state.status, Status::Review);
        assert_eq!(state.review_rounds, 1);

        let state = DocState::apply_all(&[Event::Submit, Event::Submit]);
        assert_eq!(state.status, Status::Review);
        assert_eq!(state.review_rounds, 1, "resubmitting while already in review should be ignored");
    }

    #[test]
    fn approve_requires_review_and_sets_flag() {
        let state = DocState::apply_all(&[Event::Approve]);
        assert_eq!(state.status, Status::Draft, "approve from draft must be ignored");
        assert!(!state.approved_at_least_once);

        let state = DocState::apply_all(&[Event::Submit, Event::Approve]);
        assert_eq!(state.status, Status::Approved);
        assert!(state.approved_at_least_once);
    }

    #[test]
    fn reject_and_revise_flow_back_to_draft() {
        let state = DocState::apply_all(&[Event::Submit, Event::Reject]);
        assert_eq!(state.status, Status::Rejected);

        let state = DocState::apply_all(&[Event::Submit, Event::Reject, Event::Revise]);
        assert_eq!(state.status, Status::Draft);

        let state = DocState::apply_all(&[Event::Revise]);
        assert_eq!(state.status, Status::Draft, "revise outside rejected should do nothing");
    }

    #[test]
    fn publish_requires_prior_approval_and_currently_approved() {
        let state = DocState::apply_all(&[Event::Submit, Event::Publish]);
        assert_eq!(state.status, Status::Review, "cannot publish directly from review");

        let state = DocState::apply_all(&[Event::Submit, Event::Approve, Event::Publish]);
        assert_eq!(state.status, Status::Published);
        assert!(state.approved_at_least_once);
    }

    #[test]
    fn archive_only_from_published_and_restore_targets_previous_kind() {
        let state = DocState::apply_all(&[Event::Archive]);
        assert_eq!(state.status, Status::Draft, "cannot archive draft");
        assert_eq!(state.archive_count, 0);

        let state = DocState::apply_all(&[
            Event::Submit,
            Event::Approve,
            Event::Publish,
            Event::Archive,
        ]);
        assert_eq!(state.status, Status::Archived);
        assert_eq!(state.archive_count, 1);

        let state = DocState::apply_all(&[
            Event::Submit,
            Event::Approve,
            Event::Publish,
            Event::Archive,
            Event::Restore,
        ]);
        assert_eq!(state.status, Status::Published, "restoring an archived published document should return to published");
    }

    #[test]
    fn restore_from_archived_rejected_returns_to_rejected() {
        let state = DocState::apply_all(&[
            Event::Submit,
            Event::Reject,
            Event::Archive,
            Event::Restore,
        ]);
        assert_eq!(state.status, Status::Rejected);
        assert_eq!(state.archive_count, 1);
    }
}
