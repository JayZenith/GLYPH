#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Channel {
    Email,
    Sms,
    Push,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Welcome,
    PasswordReset,
    BillingFailed { amount_due_cents: u32 },
    WeeklyDigest { unread_count: u32 },
    SecurityAlert { urgent: bool },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeliveryPlan {
    pub channel: Channel,
    pub priority: u8,
    pub template: &'static str,
    pub retry: bool,
}

pub fn plan(event: Event) -> DeliveryPlan {
    match event {
        Event::Welcome => DeliveryPlan {
            channel: Channel::Push,
            priority: 1,
            template: "welcome_email",
            retry: false,
        },
        Event::PasswordReset => DeliveryPlan {
            channel: Channel::Sms,
            priority: 4,
            template: "reset_sms",
            retry: true,
        },
        Event::BillingFailed { amount_due_cents } => DeliveryPlan {
            channel: Channel::Email,
            priority: if amount_due_cents > 10_000 { 3 } else { 2 },
            template: "billing_failed",
            retry: false,
        },
        Event::WeeklyDigest { unread_count } => DeliveryPlan {
            channel: Channel::Email,
            priority: if unread_count == 0 { 0 } else { 1 },
            template: "weekly_digest",
            retry: false,
        },
        Event::SecurityAlert { urgent } => DeliveryPlan {
            channel: if urgent { Channel::Email } else { Channel::Push },
            priority: if urgent { 5 } else { 2 },
            template: if urgent { "security_alert" } else { "security_notice" },
            retry: true,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn welcome_uses_email_template_and_retryable_send() {
        let got = plan(Event::Welcome);
        assert_eq!(
            got,
            DeliveryPlan {
                channel: Channel::Email,
                priority: 1,
                template: "welcome_email",
                retry: true,
            }
        );
    }

    #[test]
    fn password_reset_is_high_priority_email() {
        let got = plan(Event::PasswordReset);
        assert_eq!(
            got,
            DeliveryPlan {
                channel: Channel::Email,
                priority: 5,
                template: "reset_email",
                retry: true,
            }
        );
    }

    #[test]
    fn large_billing_failure_uses_sms_and_retries() {
        let got = plan(Event::BillingFailed {
            amount_due_cents: 25_000,
        });
        assert_eq!(
            got,
            DeliveryPlan {
                channel: Channel::Sms,
                priority: 3,
                template: "billing_failed_sms",
                retry: true,
            }
        );
    }

    #[test]
    fn zero_unread_digest_is_suppressed_to_push_summary() {
        let got = plan(Event::WeeklyDigest { unread_count: 0 });
        assert_eq!(
            got,
            DeliveryPlan {
                channel: Channel::Push,
                priority: 0,
                template: "digest_idle",
                retry: false,
            }
        );
    }

    #[test]
    fn urgent_security_alert_uses_sms_but_same_template() {
        let got = plan(Event::SecurityAlert { urgent: true });
        assert_eq!(
            got,
            DeliveryPlan {
                channel: Channel::Sms,
                priority: 5,
                template: "security_alert",
                retry: true,
            }
        );
    }
}
