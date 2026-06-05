enum Speed {
    Standard,
    Express,
    Overnight,
}

enum Zone {
    Domestic,
    International,
}

enum Command {
    Ship { speed: Speed, zone: Zone, fragile: bool, heavy: bool },
    Hold { refrigerated: bool, heavy: bool },
    Return { zone: Zone, pickup: bool },
}

struct Job {
    id: &'static str,
    cmd: Command,
}

fn label(cmd: &Command) -> &'static str {
    match cmd {
        Command::Ship { speed: Speed::Overnight, .. } => "OVERNIGHT",
        Command::Ship { zone: Zone::International, .. } => "EXPORT",
        Command::Ship { heavy: true, .. } => "FREIGHT-STANDARD",
        Command::Ship { speed: Speed::Express, fragile: true, .. } => "RUSH-FRAGILE",
        Command::Ship { speed: Speed::Standard, .. } => "STANDARD",
        Command::Hold { refrigerated: true, .. } => "COLD-HOLD",
        Command::Hold { .. } => "HOLD",
        Command::Return { pickup: true, .. } => "RETURN-PICKUP",
        Command::Return { .. } => "RETURN",
    }
}

fn main() {
    let jobs = [
        Job {
            id: "A1",
            cmd: Command::Ship {
                speed: Speed::Overnight,
                zone: Zone::Domestic,
                fragile: false,
                heavy: false,
            },
        },
        Job {
            id: "A2",
            cmd: Command::Hold {
                refrigerated: false,
                heavy: true,
            },
        },
        Job {
            id: "A3",
            cmd: Command::Ship {
                speed: Speed::Standard,
                zone: Zone::International,
                fragile: false,
                heavy: true,
            },
        },
        Job {
            id: "A4",
            cmd: Command::Return {
                zone: Zone::Domestic,
                pickup: true,
            },
        },
        Job {
            id: "A5",
            cmd: Command::Ship {
                speed: Speed::Standard,
                zone: Zone::Domestic,
                fragile: false,
                heavy: true,
            },
        },
        Job {
            id: "A6",
            cmd: Command::Ship {
                speed: Speed::Overnight,
                zone: Zone::International,
                fragile: false,
                heavy: false,
            },
        },
        Job {
            id: "A7",
            cmd: Command::Hold {
                refrigerated: true,
                heavy: true,
            },
        },
        Job {
            id: "A8",
            cmd: Command::Return {
                zone: Zone::International,
                pickup: false,
            },
        },
    ];

    for job in jobs {
        println!("{} => {}", job.id, label(&job.cmd));
    }
}
