#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PaymentAction {
    Authorize { amount: u32, card_present: bool },
    Capture { amount: u32, prior_auth: bool },
    Refund { amount: u32, original_capture: bool },
    Void,
}

pub fn classify(action: PaymentAction) -> &'static str {
    match action {
        PaymentAction::Authorize { amount, .. } => {
            if amount >= 1000 {
                "manual_review"
            } else {
                "approve"
            }
        }
        PaymentAction::Capture { prior_auth, .. } => {
            if prior_auth {
                "settle"
            } else {
                "approve"
            }
        }
        PaymentAction::Refund { amount, original_capture } => {
            if original_capture && amount < 500 {
                "refund"
            } else {
                "reject"
            }
        }
        PaymentAction::Void => "settle",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn authorize_requires_chip_for_large_amounts() {
        assert_eq!(
            classify(PaymentAction::Authorize {
                amount: 1500,
                card_present: true,
            }),
            "approve"
        );
        assert_eq!(
            classify(PaymentAction::Authorize {
                amount: 1500,
                card_present: false,
            }),
            "manual_review"
        );
    }

    #[test]
    fn capture_without_auth_is_rejected() {
        assert_eq!(
            classify(PaymentAction::Capture {
                amount: 200,
                prior_auth: false,
            }),
            "reject"
        );
        assert_eq!(
            classify(PaymentAction::Capture {
                amount: 200,
                prior_auth: true,
            }),
            "settle"
        );
    }

    #[test]
    fn refund_needs_original_capture_and_allows_boundary() {
        assert_eq!(
            classify(PaymentAction::Refund {
                amount: 500,
                original_capture: true,
            }),
            "refund"
        );
        assert_eq!(
            classify(PaymentAction::Refund {
                amount: 100,
                original_capture: false,
            }),
            "reject"
        );
    }

    #[test]
    fn void_maps_to_cancel() {
        assert_eq!(classify(PaymentAction::Void), "cancel");
    }
}
