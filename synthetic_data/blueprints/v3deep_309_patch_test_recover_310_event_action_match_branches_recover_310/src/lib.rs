#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Channel {
    Email,
    Sms,
    Push,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Priority {
    Low,
    Normal,
    High,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    Welcome,
    PasswordReset,
    InvoiceReady,
    FraudAlert,
    Digest,
}

pub fn action_for(event: Event, channel: Channel, priority: Priority, quiet_hours: bool) -> &'static str {
    match event {
        Event::Welcome => match channel {
            Channel::Email => "send_welcome_email",
            Channel::Sms => "send_sms",
            Channel::Push => "send_push",
        },
        Event::PasswordReset => match channel {
            Channel::Email => "send_reset_email",
            Channel::Sms => "queue_sms",
            Channel::Push => "send_push",
        },
        Event::InvoiceReady => match channel {
            Channel::Email => "send_invoice_email",
            Channel::Sms => "queue_sms",
            Channel::Push => "send_push",
        },
        Event::FraudAlert => {
            if quiet_hours {
                "queue_email"
            } else {
                match channel {
                    Channel::Email => "send_security_email",
                    Channel::Sms => "send_sms",
                    Channel::Push => "send_push",
                }
            }
        }
        Event::Digest => {
            if priority == Priority::High {
                "send_digest_now"
            } else {
                match channel {
                    Channel::Email => "send_digest_email",
                    Channel::Sms => "queue_sms",
                    Channel::Push => "drop",
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn welcome_uses_channel_specific_templates() {
        assert_eq!(action_for(Event::Welcome, Channel::Email, Priority::Normal, false), "send_welcome_email");
        assert_eq!(action_for(Event::Welcome, Channel::Sms, Priority::Normal, false), "send_welcome_sms");
        assert_eq!(action_for(Event::Welcome, Channel::Push, Priority::Normal, false), "send_welcome_push");
    }

    #[test]
    fn password_reset_is_immediate_for_all_channels() {
        assert_eq!(action_for(Event::PasswordReset, Channel::Email, Priority::Low, true), "send_reset_email");
        assert_eq!(action_for(Event::PasswordReset, Channel::Sms, Priority::Low, true), "send_reset_sms");
        assert_eq!(action_for(Event::PasswordReset, Channel::Push, Priority::Low, true), "send_reset_push");
    }

    #[test]
    fn invoice_ready_respects_channel_capabilities() {
        assert_eq!(action_for(Event::InvoiceReady, Channel::Email, Priority::Normal, false), "send_invoice_email");
        assert_eq!(action_for(Event::InvoiceReady, Channel::Sms, Priority::Normal, false), "queue_sms_invoice_summary");
        assert_eq!(action_for(Event::InvoiceReady, Channel::Push, Priority::Normal, false), "drop");
    }

    #[test]
    fn fraud_alert_overrides_quiet_hours_for_urgent_channels() {
        assert_eq!(action_for(Event::FraudAlert, Channel::Email, Priority::High, true), "send_security_email");
        assert_eq!(action_for(Event::FraudAlert, Channel::Sms, Priority::High, true), "send_security_sms");
        assert_eq!(action_for(Event::FraudAlert, Channel::Push, Priority::High, true), "send_security_push");
        assert_eq!(action_for(Event::FraudAlert, Channel::Email, Priority::Normal, true), "queue_email");
    }

    #[test]
    fn digest_depends_on_priority_and_channel() {
        assert_eq!(action_for(Event::Digest, Channel::Email, Priority::Low, false), "send_digest_email");
        assert_eq!(action_for(Event::Digest, Channel::Sms, Priority::Normal, false), "queue_sms_digest_summary");
        assert_eq!(action_for(Event::Digest, Channel::Push, Priority::Normal, false), "drop");
        assert_eq!(action_for(Event::Digest, Channel::Email, Priority::High, false), "send_digest_now");
        assert_eq!(action_for(Event::Digest, Channel::Push, Priority::High, false), "send_digest_now");
    }
}
