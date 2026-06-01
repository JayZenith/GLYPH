#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Draft,
    Submitted,
    Approved,
    Rejected,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Submit,
    Approve,
    Reject,
    Reopen,
}

pub fn apply_event(status: Status, event: Event) -> Status {
    match (status, event) {
        (Status::Draft, Event::Submit) => Status::Submitted,
        (Status::Submitted, Event::Approve) => Status::Submitted,
        (Status::Submitted, Event::Reject) => Status::Rejected,
        (Status::Rejected, Event::Reopen) => Status::Submitted,
        (Status::Approved, Event::Reopen) => Status::Draft,
        (s, _) => s,
    }
}

pub fn apply_events(mut status: Status, events: &[Event]) -> Status {
    for event in events {
        status = apply_event(status, event.clone());
    }
    status
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn approves_after_submission() {
        assert_eq!(
            apply_events(Status::Draft, &[Event::Submit, Event::Approve]),
            Status::Approved
        );
    }

    #[test]
    fn rejected_order_reopens_to_draft() {
        assert_eq!(
            apply_events(Status::Draft, &[Event::Submit, Event::Reject, Event::Reopen]),
            Status::Draft
        );
    }

    #[test]
    fn approved_order_stays_approved_when_reopened() {
        assert_eq!(
            apply_events(Status::Draft, &[Event::Submit, Event::Approve, Event::Reopen]),
            Status::Approved
        );
    }

    #[test]
    fn submit_from_rejected_has_no_effect() {
        assert_eq!(
            apply_events(Status::Rejected, &[Event::Submit]),
            Status::Rejected
        );
    }
}
