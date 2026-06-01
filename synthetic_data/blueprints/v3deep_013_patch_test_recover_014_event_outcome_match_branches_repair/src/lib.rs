#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Login { success: bool, mfa_required: bool },
    Payment { captured: bool, refunded: bool, disputed: bool },
    Shipment { delivered: bool, returned: bool, lost: bool },
    Ticket { closed: bool, escalated: bool, reopened: bool },
}

pub fn outcome(event: Event) -> &'static str {
    match event {
        Event::Login { success, .. } => {
            if success { "ok" } else { "retry" }
        }
        Event::Payment { captured, .. } => {
            if captured { "paid" } else { "pending" }
        }
        Event::Shipment { delivered, .. } => {
            if delivered { "complete" } else { "in_transit" }
        }
        Event::Ticket { closed, .. } => {
            if closed { "resolved" } else { "open" }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{outcome, Event};

    #[test]
    fn login_mfa_needed_is_challenge() {
        assert_eq!(
            outcome(Event::Login {
                success: false,
                mfa_required: true,
            }),
            "challenge"
        );
    }

    #[test]
    fn refunded_payment_wins_over_captured() {
        assert_eq!(
            outcome(Event::Payment {
                captured: true,
                refunded: true,
                disputed: false,
            }),
            "refunded"
        );
    }

    #[test]
    fn disputed_payment_wins_over_all_other_payment_states() {
        assert_eq!(
            outcome(Event::Payment {
                captured: true,
                refunded: true,
                disputed: true,
            }),
            "hold"
        );
    }

    #[test]
    fn returned_shipment_is_not_complete() {
        assert_eq!(
            outcome(Event::Shipment {
                delivered: true,
                returned: true,
                lost: false,
            }),
            "returned"
        );
    }

    #[test]
    fn lost_shipment_wins_over_delivery_flags() {
        assert_eq!(
            outcome(Event::Shipment {
                delivered: true,
                returned: true,
                lost: true,
            }),
            "lost"
        );
    }

    #[test]
    fn reopened_ticket_is_active_even_if_closed() {
        assert_eq!(
            outcome(Event::Ticket {
                closed: true,
                escalated: false,
                reopened: true,
            }),
            "active"
        );
    }

    #[test]
    fn escalated_open_ticket_is_priority() {
        assert_eq!(
            outcome(Event::Ticket {
                closed: false,
                escalated: true,
                reopened: false,
            }),
            "priority"
        );
    }
}
