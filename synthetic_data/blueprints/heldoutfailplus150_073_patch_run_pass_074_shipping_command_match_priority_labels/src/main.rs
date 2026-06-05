enum Command {
    Ship,
    Hold,
    Label,
}

enum CargoKind {
    Standard,
    Frozen,
    Bulk,
    Returns,
}

struct Order<'a> {
    raw: &'a str,
    command: Command,
    priority: bool,
    cargo: CargoKind,
}

fn label(order: &Order) -> &'static str {
    match order.command {
        Command::Ship => {
            if order.priority {
                "EXPRESS"
            } else {
                match order.cargo {
                    CargoKind::Frozen => "COLD-CHAIN",
                    CargoKind::Bulk => "FREIGHT",
                    CargoKind::Returns => "STANDARD",
                    CargoKind::Standard => "STANDARD",
                }
            }
        }
        Command::Hold => "HOLD",
        Command::Label => {
            if order.priority {
                "EXPRESS"
            } else {
                "STANDARD"
            }
        }
    }
}

fn main() {
    let orders = [
        Order { raw: "ship-now", command: Command::Ship, priority: true, cargo: CargoKind::Standard },
        Order { raw: "ship-frozen", command: Command::Ship, priority: false, cargo: CargoKind::Frozen },
        Order { raw: "ship-frozen-priority", command: Command::Ship, priority: true, cargo: CargoKind::Frozen },
        Order { raw: "ship-bulk", command: Command::Ship, priority: false, cargo: CargoKind::Bulk },
        Order { raw: "ship-bulk-priority", command: Command::Ship, priority: true, cargo: CargoKind::Bulk },
        Order { raw: "ship-returns", command: Command::Ship, priority: false, cargo: CargoKind::Returns },
        Order { raw: "ship-returns-priority", command: Command::Ship, priority: true, cargo: CargoKind::Returns },
        Order { raw: "hold-bulk", command: Command::Hold, priority: false, cargo: CargoKind::Bulk },
        Order { raw: "label", command: Command::Label, priority: false, cargo: CargoKind::Standard },
    ];

    for order in orders {
        println!("{} => {}", order.raw, label(&order));
    }
}
