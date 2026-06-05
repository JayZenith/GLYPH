enum Ticket {
    Alarm { id: &'static str, severity: u8, acknowledged: bool, minute: u32 },
    Job { id: &'static str, attempts: u8, queued: bool, minute: u32 },
    Gate { id: &'static str, open: bool, locked: bool, minute: u32 },
    Sync { id: &'static str, active: bool, lag: u8, minute: u32 },
}

fn fmt_time(minute: u32) -> String {
    format!("{:02}:{:02}", minute / 60, minute % 60)
}

fn summarize(t: &Ticket) -> String {
    match t {
        Ticket::Alarm { id, severity, acknowledged, minute } => {
            let label = if *acknowledged {
                "ack"
            } else if *severity >= 8 {
                "high"
            } else {
                "low"
            };
            format!("{} {} @ {}", id, label, fmt_time(*minute))
        }
        Ticket::Job { id, attempts, queued, minute } => {
            let label = if *attempts > 0 {
                format!("retry {}", attempts)
            } else if *queued {
                "queued".to_string()
            } else {
                "fresh".to_string()
            };
            format!("{} {} @ {}", id, label, fmt_time(*minute))
        }
        Ticket::Gate { id, open, locked, minute } => {
            let label = if *open {
                "open"
            } else if *locked {
                "locked"
            } else {
                "closed"
            };
            format!("{} {} @ {}", id, label, fmt_time(*minute))
        }
        Ticket::Sync { id, active, lag, minute } => {
            let label = if *lag >= 3 {
                format!("lag {}", lag)
            } else if *active {
                "active".to_string()
            } else {
                "idle".to_string()
            };
            format!("{} {} @ {}", id, label, fmt_time(*minute))
        }
    }
}

fn main() {
    let items = vec![
        Ticket::Alarm { id: "A1", severity: 9, acknowledged: true, minute: 540 },
        Ticket::Job { id: "A2", attempts: 0, queued: true, minute: 540 },
        Ticket::Gate { id: "B7", open: false, locked: true, minute: 510 },
        Ticket::Job { id: "C3", attempts: 3, queued: true, minute: 525 },
        Ticket::Job { id: "C4", attempts: 1, queued: false, minute: 530 },
        Ticket::Sync { id: "D2", active: true, lag: 5, minute: 520 },
        Ticket::Alarm { id: "E9", severity: 2, acknowledged: false, minute: 500 },
    ];

    for item in &items {
        println!("{}", summarize(item));
    }
}
