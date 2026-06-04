enum Command {
    Ship {
        express: bool,
        international: bool,
        hazard: bool,
        cold: bool,
        bulk: bool,
        weight_kg: u32,
    },
    Return {
        hazard: bool,
        manual_review: bool,
    },
    Hold,
}

fn label(cmd: &Command) -> &'static str {
    match cmd {
        Command::Ship { express: true, .. } => "EXPRESS",
        Command::Ship { international: true, .. } => "INTERNATIONAL",
        Command::Ship { hazard: true, .. } => "HAZARD",
        Command::Ship { cold: true, .. } => "COLD",
        Command::Ship { bulk: true, .. } => "BULK",
        Command::Ship { weight_kg, .. } if *weight_kg >= 20 => "HEAVY",
        Command::Ship { .. } => "STANDARD",
        Command::Return { hazard: true, .. } => "RETURN",
        Command::Return { .. } => "RETURN",
        Command::Hold => "HOLD",
    }
}

fn main() {
    let cases = [
        ("express lane", Command::Ship { express: true, international: false, hazard: false, cold: false, bulk: false, weight_kg: 32 }),
        ("batch lane", Command::Ship { express: false, international: false, hazard: false, cold: false, bulk: true, weight_kg: 8 }),
        ("returns desk", Command::Return { hazard: true, manual_review: false }),
        ("customs desk", Command::Ship { express: false, international: true, hazard: false, cold: false, bulk: false, weight_kg: 27 }),
        ("cold chain", Command::Ship { express: true, international: false, hazard: false, cold: true, bulk: false, weight_kg: 4 }),
        ("standard queue", Command::Return { hazard: false, manual_review: false }),
        ("manual review", Command::Return { hazard: false, manual_review: true }),
        ("local dispatch", Command::Ship { express: false, international: false, hazard: false, cold: false, bulk: false, weight_kg: 3 }),
    ];

    for (name, cmd) in cases {
        println!("{} => {}", name, label(&cmd));
    }
}
