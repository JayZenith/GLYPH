enum Command {
    Hold,
    Release,
    Expedite,
    Reroute,
}

enum Zone {
    Domestic,
    International,
}

enum Temp {
    Ambient,
    Cold,
}

struct Package {
    id: &'static str,
    command: Option<Command>,
    zone: Zone,
    temp: Temp,
    urgent: bool,
    signature: bool,
    oversize: bool,
    paperwork_missing: bool,
}

fn label(pkg: &Package) -> String {
    match pkg.command {
        Some(Command::Hold) => "hold for review".to_string(),
        Some(Command::Expedite) if pkg.urgent => "urgent overnight".to_string(),
        Some(Command::Reroute) => match pkg.zone {
            Zone::International => "reroute to export desk".to_string(),
            Zone::Domestic => "reroute to local hub".to_string(),
        },
        Some(Command::Release) => {
            if pkg.oversize {
                "ground freight".to_string()
            } else {
                "release standard".to_string()
            }
        }
        None => {
            if pkg.paperwork_missing {
                "hold missing paperwork".to_string()
            } else {
                "no action".to_string()
            }
        }
        Some(Command::Expedite) => "expedite".to_string(),
    }
}

fn main() {
    let packages = [
        Package {
            id: "P1",
            command: Some(Command::Hold),
            zone: Zone::Domestic,
            temp: Temp::Ambient,
            urgent: true,
            signature: true,
            oversize: false,
            paperwork_missing: false,
        },
        Package {
            id: "P2",
            command: Some(Command::Expedite),
            zone: Zone::Domestic,
            temp: Temp::Ambient,
            urgent: true,
            signature: true,
            oversize: false,
            paperwork_missing: false,
        },
        Package {
            id: "P3",
            command: Some(Command::Reroute),
            zone: Zone::Domestic,
            temp: Temp::Cold,
            urgent: false,
            signature: false,
            oversize: false,
            paperwork_missing: false,
        },
        Package {
            id: "P4",
            command: Some(Command::Release),
            zone: Zone::Domestic,
            temp: Temp::Ambient,
            urgent: false,
            signature: false,
            oversize: true,
            paperwork_missing: false,
        },
        Package {
            id: "P5",
            command: None,
            zone: Zone::International,
            temp: Temp::Ambient,
            urgent: false,
            signature: false,
            oversize: false,
            paperwork_missing: true,
        },
        Package {
            id: "P6",
            command: None,
            zone: Zone::Domestic,
            temp: Temp::Ambient,
            urgent: false,
            signature: false,
            oversize: false,
            paperwork_missing: false,
        },
    ];

    for pkg in packages {
        println!("{} => {}", pkg.id, label(&pkg));
    }
}
