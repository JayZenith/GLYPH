#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Channel {
    Email,
    Sms,
    Push,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Priority {
    Low,
    Normal,
    High,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Audience {
    Internal,
    External,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Message {
    pub channel: Channel,
    pub priority: Priority,
    pub audience: Audience,
    pub has_subject: bool,
    pub has_body: bool,
    pub recipient_count: usize,
}

pub fn delivery_plan(msg: &Message) -> &'static str {
    match (&msg.channel, &msg.priority, &msg.audience) {
        (Channel::Email, _, _) => {
            if msg.recipient_count == 0 {
                "drop"
            } else if !msg.has_body {
                "send_email"
            } else {
                "queue_digest"
            }
        }
        (Channel::Sms, Priority::High, _) => {
            if msg.has_body {
                "send_sms"
            } else {
                "drop"
            }
        }
        (Channel::Sms, _, _) => "send_sms",
        (Channel::Push, _, Audience::Internal) => "send_push",
        (Channel::Push, Priority::High, Audience::External) => "queue_review",
        (Channel::Push, _, Audience::External) => {
            if msg.has_subject {
                "send_push"
            } else {
                "drop"
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn msg(
        channel: Channel,
        priority: Priority,
        audience: Audience,
        has_subject: bool,
        has_body: bool,
        recipient_count: usize,
    ) -> Message {
        Message {
            channel,
            priority,
            audience,
            has_subject,
            has_body,
            recipient_count,
        }
    }

    #[test]
    fn email_requires_recipients() {
        let m = msg(Channel::Email, Priority::Normal, Audience::External, true, true, 0);
        assert_eq!(delivery_plan(&m), "drop");
    }

    #[test]
    fn email_with_body_and_subject_sends() {
        let m = msg(Channel::Email, Priority::Normal, Audience::External, true, true, 2);
        assert_eq!(delivery_plan(&m), "send_email");
    }

    #[test]
    fn email_without_subject_becomes_draft() {
        let m = msg(Channel::Email, Priority::Low, Audience::Internal, false, true, 1);
        assert_eq!(delivery_plan(&m), "draft_email");
    }

    #[test]
    fn email_without_body_drops() {
        let m = msg(Channel::Email, Priority::High, Audience::Internal, true, false, 1);
        assert_eq!(delivery_plan(&m), "drop");
    }

    #[test]
    fn sms_high_without_body_is_queued_for_callback() {
        let m = msg(Channel::Sms, Priority::High, Audience::External, false, false, 1);
        assert_eq!(delivery_plan(&m), "queue_callback");
    }

    #[test]
    fn sms_non_high_without_body_drops() {
        let m = msg(Channel::Sms, Priority::Normal, Audience::External, false, false, 1);
        assert_eq!(delivery_plan(&m), "drop");
    }

    #[test]
    fn sms_with_body_sends() {
        let m = msg(Channel::Sms, Priority::Low, Audience::Internal, false, true, 1);
        assert_eq!(delivery_plan(&m), "send_sms");
    }

    #[test]
    fn internal_push_without_subject_still_sends() {
        let m = msg(Channel::Push, Priority::Normal, Audience::Internal, false, true, 4);
        assert_eq!(delivery_plan(&m), "send_push");
    }

    #[test]
    fn external_push_high_with_subject_escalates() {
        let m = msg(Channel::Push, Priority::High, Audience::External, true, true, 3);
        assert_eq!(delivery_plan(&m), "escalate_push");
    }

    #[test]
    fn external_push_high_without_subject_drops() {
        let m = msg(Channel::Push, Priority::High, Audience::External, false, true, 3);
        assert_eq!(delivery_plan(&m), "drop");
    }

    #[test]
    fn external_push_non_high_with_subject_sends() {
        let m = msg(Channel::Push, Priority::Normal, Audience::External, true, true, 3);
        assert_eq!(delivery_plan(&m), "send_push");
    }

    #[test]
    fn external_push_non_high_without_subject_drops() {
        let m = msg(Channel::Push, Priority::Low, Audience::External, false, true, 3);
        assert_eq!(delivery_plan(&m), "drop");
    }
}
