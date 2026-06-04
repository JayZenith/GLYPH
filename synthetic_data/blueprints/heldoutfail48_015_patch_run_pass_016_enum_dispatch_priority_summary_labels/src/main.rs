enum Ticket {
    Bug { critical: bool, customer_vip: bool },
    User { vip: bool, needs_followup: bool },
    Ops { severity: u8, after_hours: bool },
    Maintenance { emergency: bool, region: &'static str },
}

fn summarize(ticket: &Ticket) -> (&'static str, &'static str) {
    match ticket {
        Ticket::Bug { .. } => ("bug", "queue"),
        Ticket::User { vip: true, .. } => ("vip-user", "reply"),
        Ticket::User { .. } => ("user", "reply"),
        Ticket::Ops { severity, .. } if *severity >= 7 => ("ops", "page-ops"),
        Ticket::Ops { .. } => ("ops", "queue"),
        Ticket::Maintenance { .. } => ("maintenance", "schedule"),
    }
}

fn priority(ticket: &Ticket) -> &'static str {
    match ticket {
        Ticket::Bug { critical: true, .. } => "P1",
        Ticket::Bug { .. } => "P2",
        Ticket::User { vip: true, needs_followup: true } => "P1",
        Ticket::User { vip: true, .. } => "P2",
        Ticket::User { .. } => "P3",
        Ticket::Ops { severity, .. } if *severity >= 7 => "P1",
        Ticket::Ops { .. } => "P2",
        Ticket::Maintenance { emergency: true, .. } => "P1",
        Ticket::Maintenance { .. } => "P2",
    }
}

fn line(id: &str, ticket: &Ticket) -> String {
    let (label, action) = summarize(ticket);
    format!("{}:{}:{}:{}", id, label, priority(ticket), action)
}

fn main() {
    let tickets = [
        ("A", Ticket::Bug { critical: true, customer_vip: true }),
        ("B", Ticket::Bug { critical: false, customer_vip: false }),
        ("C", Ticket::Ops { severity: 8, after_hours: true }),
        ("D", Ticket::User { vip: true, needs_followup: true }),
        ("E", Ticket::User { vip: false, needs_followup: false }),
        ("F", Ticket::Maintenance { emergency: false, region: "eu-west" }),
        ("G", Ticket::Maintenance { emergency: true, region: "us-east" }),
        ("H", Ticket::User { vip: true, needs_followup: false }),
    ];

    let report = tickets
        .iter()
        .map(|(id, t)| line(id, t))
        .collect::<Vec<_>>()
        .join("\n");

    println!("{}", report);
}
