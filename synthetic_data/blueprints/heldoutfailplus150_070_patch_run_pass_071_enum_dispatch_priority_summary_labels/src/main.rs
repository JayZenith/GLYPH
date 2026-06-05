enum Event {
    Deploy { service: &'static str, actor: &'static str, urgent: bool },
    Backup { target: &'static str, nightly: bool, verified: bool },
    Report { kind: &'static str, include_empty: bool, cadence: &'static str },
    Alert { code: u16, source: &'static str, escalated: bool },
    Maintenance { system: &'static str, window: &'static str, forced: bool },
}

fn summarize(event: &Event) -> String {
    match event {
        Event::Deploy { service, .. } => format!("deploy -> {}", service),
        Event::Backup { target, verified, .. } => {
            if *verified {
                format!("backup -> {} [verified]", target)
            } else {
                format!("backup -> {}", target)
            }
        }
        Event::Report { kind, include_empty, .. } => {
            if *include_empty {
                format!("report -> {} [all]", kind)
            } else {
                format!("report -> {}", kind)
            }
        }
        Event::Alert { code, source, .. } => {
            if *code >= 500 {
                format!("alert -> {} [critical]", source)
            } else {
                format!("alert -> {}", source)
            }
        }
        Event::Maintenance { system, forced, .. } => {
            if *forced {
                format!("maintenance -> {} [forced]", system)
            } else {
                format!("maintenance -> {}", system)
            }
        }
    }
}

fn main() {
    let events = [
        Event::Deploy { service: "release", actor: "user", urgent: false },
        Event::Backup { target: "db", nightly: true, verified: true },
        Event::Report { kind: "summary", include_empty: false, cadence: "daily" },
        Event::Alert { code: 503, source: "security", escalated: true },
        Event::Alert { code: 204, source: "build", escalated: false },
        Event::Maintenance { system: "cache", window: "scheduled", forced: false },
        Event::Backup { target: "fs", nightly: false, verified: false },
        Event::Report { kind: "audit", include_empty: true, cadence: "weekly" },
    ];

    for event in events.iter() {
        println!("{}", summarize(event));
    }
}
