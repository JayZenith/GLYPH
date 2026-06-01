#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderState {
    Draft,
    Submitted,
    Approved,
    Rejected,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Submit,
    Approve,
    Reject,
    Cancel,
    Revise,
}

pub fn apply_event(state: OrderState, event: Event) -> OrderState {
    match event {
        Event::Submit => OrderState::Submitted,
        Event::Approve => OrderState::Approved,
        Event::Reject => OrderState::Rejected,
        Event::Cancel => OrderState::Cancelled,
        Event::Revise => OrderState::Draft,
    }
}

pub fn apply_events(mut state: OrderState, events: &[Event]) -> OrderState {
    for &event in events {
        state = apply_event(state, event);
    }
    state
}

#[cfg(test)]
mod tests {
    use super::{apply_event, apply_events, Event, OrderState};

    #[test]
    fn submit_only_works_from_draft() {
        assert_eq!(apply_event(OrderState::Draft, Event::Submit), OrderState::Submitted);
        assert_eq!(apply_event(OrderState::Approved, Event::Submit), OrderState::Approved);
        assert_eq!(apply_event(OrderState::Cancelled, Event::Submit), OrderState::Cancelled);
    }

    #[test]
    fn approve_requires_submitted() {
        assert_eq!(apply_event(OrderState::Submitted, Event::Approve), OrderState::Approved);
        assert_eq!(apply_event(OrderState::Draft, Event::Approve), OrderState::Draft);
        assert_eq!(apply_event(OrderState::Rejected, Event::Approve), OrderState::Rejected);
    }

    #[test]
    fn reject_requires_submitted() {
        assert_eq!(apply_event(OrderState::Submitted, Event::Reject), OrderState::Rejected);
        assert_eq!(apply_event(OrderState::Draft, Event::Reject), OrderState::Draft);
        assert_eq!(apply_event(OrderState::Approved, Event::Reject), OrderState::Approved);
    }

    #[test]
    fn revise_only_works_after_rejection() {
        assert_eq!(apply_event(OrderState::Rejected, Event::Revise), OrderState::Draft);
        assert_eq!(apply_event(OrderState::Submitted, Event::Revise), OrderState::Submitted);
        assert_eq!(apply_event(OrderState::Cancelled, Event::Revise), OrderState::Cancelled);
    }

    #[test]
    fn cancel_is_terminal_but_only_after_activity() {
        assert_eq!(apply_event(OrderState::Submitted, Event::Cancel), OrderState::Cancelled);
        assert_eq!(apply_event(OrderState::Approved, Event::Cancel), OrderState::Cancelled);
        assert_eq!(apply_event(OrderState::Draft, Event::Cancel), OrderState::Draft);
        assert_eq!(apply_event(OrderState::Cancelled, Event::Revise), OrderState::Cancelled);
        assert_eq!(apply_event(OrderState::Cancelled, Event::Approve), OrderState::Cancelled);
    }

    #[test]
    fn full_flow_and_terminal_behavior() {
        let events = [
            Event::Submit,
            Event::Reject,
            Event::Revise,
            Event::Submit,
            Event::Approve,
            Event::Cancel,
            Event::Revise,
        ];
        assert_eq!(apply_events(OrderState::Draft, &events), OrderState::Cancelled);
    }
}
