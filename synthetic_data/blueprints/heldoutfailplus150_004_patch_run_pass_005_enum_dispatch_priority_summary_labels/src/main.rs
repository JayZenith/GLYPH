enum Notice {
    Outage { id: u32, primary: bool },
    Deploy { service: &'static str, can_wait: bool },
    SecurityPatch { urgent: bool },
    UsageReport,
    Reminder { kind: &'static str },
    Chat { vip: bool },
    Digest { urgent: bool },
}

fn describe(n: &Notice) -> (u8, String, &'static str) {
    match n {
        Notice::Outage { id, .. } => (0, format!("outage#{id}"), "page"),
        Notice::Deploy { service, .. } => (1, format!("deploy {service}"), "ship"),
        Notice::SecurityPatch { .. } => (2, "security patch".to_string(), "queue"),
        Notice::UsageReport => (2, "usage report".to_string(), "batch"),
        Notice::Reminder { kind } => (2, format!("reminder {kind}"), "queue"),
        Notice::Chat { .. } => (3, "chat support".to_string(), "queue"),
        Notice::Digest { .. } => (3, "digest weekly".to_string(), "digest"),
    }
}

fn main() {
    let notices = vec![
        Notice::Outage { id: 7, primary: true },
        Notice::Deploy { service: "api", can_wait: true },
        Notice::Deploy { service: "billing", can_wait: false },
        Notice::SecurityPatch { urgent: true },
        Notice::UsageReport,
        Notice::Reminder { kind: "invoice" },
        Notice::Reminder { kind: "standup" },
        Notice::Chat { vip: true },
        Notice::Digest { urgent: false },
        Notice::Digest { urgent: true },
    ];

    for (i, n) in notices.iter().enumerate() {
        let (priority, label, route) = describe(n);
        println!("{:02}. [P{}] {} -> {}", i + 1, priority, label, route);
    }
}
