enum Mode {
    Ground,
    Air,
    Freight,
}

enum Command {
    Dispatch { mode: Mode, urgent: bool, hazmat: bool, weight_kg: u32 },
    Cancel,
    Audit,
}

struct Shipment {
    code: &'static str,
    command: Command,
}

fn command_label(cmd: &Command) -> &'static str {
    match cmd {
        Command::Cancel => "CANCELLED",
        Command::Audit => "CHECK",
        Command::Dispatch { mode, urgent, .. } => match mode {
            Mode::Air => {
                if *urgent {
                    "AIR"
                } else {
                    "STANDARD-AIR"
                }
            }
            Mode::Ground => "GROUND",
            Mode::Freight => "FREIGHT",
        },
    }
}

fn main() {
    let shipments = [
        Shipment {
            code: "route-01",
            command: Command::Dispatch {
                mode: Mode::Air,
                urgent: true,
                hazmat: false,
                weight_kg: 8,
            },
        },
        Shipment {
            code: "route-02",
            command: Command::Dispatch {
                mode: Mode::Ground,
                urgent: true,
                hazmat: true,
                weight_kg: 12,
            },
        },
        Shipment {
            code: "route-03",
            command: Command::Dispatch {
                mode: Mode::Ground,
                urgent: true,
                hazmat: false,
                weight_kg: 7,
            },
        },
        Shipment {
            code: "route-04",
            command: Command::Dispatch {
                mode: Mode::Freight,
                urgent: false,
                hazmat: false,
                weight_kg: 220,
            },
        },
        Shipment {
            code: "route-05",
            command: Command::Audit,
        },
        Shipment {
            code: "route-06",
            command: Command::Cancel,
        },
        Shipment {
            code: "route-07",
            command: Command::Dispatch {
                mode: Mode::Air,
                urgent: false,
                hazmat: false,
                weight_kg: 3,
            },
        },
    ];

    for shipment in shipments {
        println!("{} => {}", shipment.code, command_label(&shipment.command));
    }
}
