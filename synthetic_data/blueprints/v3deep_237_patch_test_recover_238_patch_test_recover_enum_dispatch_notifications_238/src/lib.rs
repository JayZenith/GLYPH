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
    Alert { severity: u8 },
    Digest { unread: u32 },
}

pub fn dispatch(channel: Channel, event: Event) -> Option<String> {
    match event {
        Event::Welcome => match channel {
            Channel::Email => Some("email:welcome".to_string()),
            Channel::Sms => Some("sms:welcome".to_string()),
            Channel::Push => None,
        },
        Event::PasswordReset => match channel {
            Channel::Email => Some("email:reset".to_string()),
            Channel::Sms => None,
            Channel::Push => Some("push:reset".to_string()),
        },
        Event::Alert { severity } => match channel {
            Channel::Email => Some(format!("email:alert:{}", severity)),
            Channel::Sms => {
                if severity >= 3 {
                    Some(format!("sms:alert:{}", severity))
                } else {
                    Some(format!("sms:alert:{}", severity))
                }
            }
            Channel::Push => {
                if severity > 1 {
                    Some(format!("push:alert:{}", severity))
                } else {
                    None
                }
            }
        },
        Event::Digest { unread } => match channel {
            Channel::Email => {
                if unread == 0 {
                    None
                } else {
                    Some(format!("email:digest:{}", unread))
                }
            }
            Channel::Sms => {
                if unread > 5 {
                    Some(format!("sms:digest:{}", unread))
                } else {
                    None
                }
            }
            Channel::Push => Some(format!("push:digest:{}", unread)),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{dispatch, Channel, Event};

    #[test]
    fn welcome_and_reset_routes_match_supported_channels() {
        assert_eq!(dispatch(Channel::Email, Event::Welcome), Some("email:welcome".into()));
        assert_eq!(dispatch(Channel::Sms, Event::Welcome), Some("sms:welcome".into()));
        assert_eq!(dispatch(Channel::Push, Event::Welcome), Some("push:welcome".into()));

        assert_eq!(dispatch(Channel::Email, Event::PasswordReset), Some("email:reset".into()));
        assert_eq!(dispatch(Channel::Sms, Event::PasswordReset), Some("sms:reset".into()));
        assert_eq!(dispatch(Channel::Push, Event::PasswordReset), Some("push:reset".into()));
    }

    #[test]
    fn alerts_only_reach_channels_allowed_by_severity() {
        assert_eq!(dispatch(Channel::Email, Event::Alert { severity: 1 }), Some("email:alert:1".into()));
        assert_eq!(dispatch(Channel::Sms, Event::Alert { severity: 2 }), None);
        assert_eq!(dispatch(Channel::Sms, Event::Alert { severity: 3 }), Some("sms:alert:3".into()));
        assert_eq!(dispatch(Channel::Push, Event::Alert { severity: 1 }), Some("push:alert:1".into()));
    }

    #[test]
    fn digest_delivery_has_channel_specific_thresholds() {
        assert_eq!(dispatch(Channel::Email, Event::Digest { unread: 0 }), None);
        assert_eq!(dispatch(Channel::Email, Event::Digest { unread: 2 }), Some("email:digest:2".into()));
        assert_eq!(dispatch(Channel::Sms, Event::Digest { unread: 5 }), Some("sms:digest:5".into()));
        assert_eq!(dispatch(Channel::Sms, Event::Digest { unread: 4 }), None);
        assert_eq!(dispatch(Channel::Push, Event::Digest { unread: 0 }), None);
        assert_eq!(dispatch(Channel::Push, Event::Digest { unread: 7 }), Some("push:digest:7".into()));
    }
}
