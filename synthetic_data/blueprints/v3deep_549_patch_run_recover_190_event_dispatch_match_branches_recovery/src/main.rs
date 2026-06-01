enum Command {
    Ship { id: u32, priority: bool, zone: u8 },
    Gift { to: &'static str, item: &'static str, qty: u8, fragile: bool },
    Restock { sku: &'static str, qty: u8 },
    Audit { day: &'static str, entries: u8 },
}

fn render(cmd: &Command) -> String {
    match cmd {
        Command::Ship { id, priority, zone } => {
            if *priority {
                format!("ship:{}@{}", zone, id)
            } else {
                format!("ship:{}@{}", id, zone)
            }
        }
        Command::Gift { to, item, qty, fragile } => {
            let suffix = if *fragile { "" } else { " [fragile]" };
            format!("gift:{}->{}x{}{}", item, to, qty, suffix)
        }
        Command::Restock { sku, qty } => format!("restock:{}x{}", qty, sku),
        Command::Audit { day, entries } => format!("audit:{} total={}", entries, day),
    }
}

fn main() {
    let cmds = [
        Command::Ship {
            id: 3,
            priority: true,
            zone: 2,
        },
        Command::Gift {
            to: "Ada",
            item: "Book",
            qty: 2,
            fragile: true,
        },
        Command::Restock { sku: "Bolt", qty: 5 },
        Command::Audit {
            day: "2024-03",
            entries: 4,
        },
    ];

    for cmd in cmds.iter() {
        println!("{}", render(cmd));
    }
}
