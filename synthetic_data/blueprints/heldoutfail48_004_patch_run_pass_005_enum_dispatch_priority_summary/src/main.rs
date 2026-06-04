enum Ticket {
    Fraud { urgent: bool, vip: bool },
    Payment { disputed: bool, vip: bool },
    Account { locked: bool, vip: bool },
    Archived,
}

struct Task {
    code: &'static str,
    ticket: Ticket,
}

fn label(ticket: &Ticket) -> String {
    match ticket {
        Ticket::Fraud { urgent, vip } => {
            if *vip {
                "queue:vip".to_string()
            } else if *urgent {
                "alert:fraud".to_string()
            } else {
                "queue:standard".to_string()
            }
        }
        Ticket::Payment { disputed, vip } => {
            if *disputed {
                "review:manual".to_string()
            } else if *vip {
                "queue:vip".to_string()
            } else {
                "queue:standard".to_string()
            }
        }
        Ticket::Account { locked, vip } => {
            if *locked {
                "hold:vip-review".to_string()
            } else if *vip {
                "queue:vip".to_string()
            } else {
                "queue:standard".to_string()
            }
        }
        Ticket::Archived => "queue:standard".to_string(),
    }
}

fn main() {
    let tasks = vec![
        Task {
            code: "A1",
            ticket: Ticket::Fraud {
                urgent: true,
                vip: false,
            },
        },
        Task {
            code: "B2",
            ticket: Ticket::Account {
                locked: true,
                vip: true,
            },
        },
        Task {
            code: "C3",
            ticket: Ticket::Payment {
                disputed: true,
                vip: false,
            },
        },
        Task {
            code: "D4",
            ticket: Ticket::Payment {
                disputed: false,
                vip: true,
            },
        },
        Task {
            code: "E5",
            ticket: Ticket::Account {
                locked: false,
                vip: false,
            },
        },
        Task {
            code: "F6",
            ticket: Ticket::Archived,
        },
    ];

    let out = tasks
        .iter()
        .map(|task| format!("{} => {}", task.code, label(&task.ticket)))
        .collect::<Vec<_>>()
        .join("\n");

    print!("{}", out);
}
