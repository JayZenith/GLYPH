#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Draft,
    Review,
    Approved,
    Published,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Submit,
    Approve,
    Publish,
    Reject,
    Revise,
}

pub fn apply_events(events: &[Event]) -> Status {
    let mut status = Status::Draft;
    for event in events {
        status = match (status, event) {
            (Status::Draft, Event::Submit) => Status::Review,
            (Status::Review, Event::Approve) => Status::Approved,
            (Status::Approved, Event::Publish) => Status::Published,
            (Status::Review, Event::Reject) => Status::Rejected,
            (Status::Rejected, Event::Revise) => Status::Review,
            (_, Event::Reject) => Status::Rejected,
            (_, Event::Revise) => Status::Draft,
            _ => status,
        };
    }
    status
}

#[cfg(test)]
mod tests {
    use super::{apply_events, Event, Status};

    #[test]
    fn happy_path_reaches_published() {
        let events = [Event::Submit, Event::Approve, Event::Publish];
        assert_eq!(apply_events(&events), Status::Published);
    }

    #[test]
    fn reject_only_works_from_review() {
        let events = [Event::Reject];
        assert_eq!(apply_events(&events), Status::Draft);
    }

    #[test]
    fn revise_from_rejected_goes_back_to_draft() {
        let events = [Event::Submit, Event::Reject, Event::Revise];
        assert_eq!(apply_events(&events), Status::Draft);
    }

    #[test]
    fn revise_from_other_states_is_ignored() {
        let events = [Event::Revise, Event::Submit, Event::Approve, Event::Revise];
        assert_eq!(apply_events(&events), Status::Approved);
    }

    #[test]
    fn published_is_terminal() {
        let events = [
            Event::Submit,
            Event::Approve,
            Event::Publish,
            Event::Reject,
            Event::Revise,
            Event::Submit,
        ];
        assert_eq!(apply_events(&events), Status::Published);
    }
}
