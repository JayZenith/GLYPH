enum Notice {
    Incident { sev: u8, acknowledged: bool },
    Audit { actor: &'static str, strict: bool },
    Message { topic: &'static str, important: bool },
    Heartbeat,
    Security { level: u8, during_quiet_hours: bool },
}

struct Entry {
    code: &'static str,
    notice: Notice,
}

fn dispatch_label(n: &Notice) -> &'static str {
    match n {
        Notice::Incident { sev, .. } if *sev >= 4 => "ticket-urgent",
        Notice::Incident { .. } => "log-info",
        Notice::Audit { strict: true, .. } => "log-audit",
        Notice::Audit { .. } => "ticket-compliance",
        Notice::Message { important: true, .. } => "log-info",
        Notice::Message { .. } => "ignore-debug",
        Notice::Heartbeat => "ignore-debug",
        Notice::Security { during_quiet_hours: true, .. } => "ignore-debug",
        Notice::Security { level, .. } if *level >= 8 => "ticket-security",
        Notice::Security { .. } => "page-security",
    }
}

fn main() {
    let entries = [
        Entry { code: "A1", notice: Notice::Incident { sev: 5, acknowledged: false } },
        Entry { code: "A2", notice: Notice::Incident { sev: 4, acknowledged: true } },
        Entry { code: "A3", notice: Notice::Message { topic: "ops", important: true } },
        Entry { code: "A4", notice: Notice::Audit { actor: "bot", strict: false } },
        Entry { code: "A5", notice: Notice::Security { level: 7, during_quiet_hours: false } },
        Entry { code: "A6", notice: Notice::Heartbeat },
        Entry { code: "A7", notice: Notice::Incident { sev: 2, acknowledged: false } },
        Entry { code: "A8", notice: Notice::Security { level: 9, during_quiet_hours: false } },
        Entry { code: "A9", notice: Notice::Security { level: 10, during_quiet_hours: true } },
    ];

    for e in entries {
        println!("{} => {}", e.code, dispatch_label(&e.notice));
    }
}
