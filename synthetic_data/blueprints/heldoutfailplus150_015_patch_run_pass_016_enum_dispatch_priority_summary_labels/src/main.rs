enum Task {
    Email { customer_vip: bool, unread: u8 },
    Refund { amount_cents: u32, flagged: bool },
    Ship { express: bool, hold: bool },
    Inventory { audit: bool, delta: i32 },
    Ping,
}

fn summarize(task: &Task) -> &'static str {
    match task {
        Task::Email { .. } => "email -> notify",
        Task::Refund { .. } => "refund -> finance",
        Task::Ship { express: true, .. } => "ship-express -> warehouse/expedite",
        Task::Ship { .. } => "ship -> warehouse",
        Task::Inventory { delta, .. } if *delta != 0 => "inventory -> ops",
        Task::Inventory { .. } => "inventory-idle -> ignore",
        Task::Ping => "ping -> noop",
    }
}

fn main() {
    let tasks = [
        Task::Email { customer_vip: true, unread: 1 },
        Task::Email { customer_vip: false, unread: 3 },
        Task::Refund { amount_cents: 2500, flagged: true },
        Task::Refund { amount_cents: 500, flagged: false },
        Task::Ship { express: false, hold: true },
        Task::Ship { express: true, hold: false },
        Task::Ship { express: false, hold: false },
        Task::Inventory { audit: true, delta: 0 },
        Task::Inventory { audit: false, delta: 7 },
        Task::Ping,
    ];

    for task in tasks.iter() {
        println!("{}", summarize(task));
    }
}
