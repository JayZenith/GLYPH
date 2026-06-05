enum Action {
    Alert { urgent: bool, acknowledged: bool },
    Job { queued: bool, interactive: bool },
    Mode { safe: bool, override_lock: bool },
    Access { admin: bool, maintenance: bool },
    Route { primary: bool, disabled: bool },
    Other,
}

fn summarize(action: &Action) -> &'static str {
    match action {
        Action::Alert { urgent, .. } => {
            if *urgent { "ALERT/escalate" } else { "ALERT/retry" }
        }
        Action::Job { queued, .. } => {
            if *queued { "JOB/batch" } else { "JOB/interactive" }
        }
        Action::Mode { safe, .. } => {
            if *safe { "MODE/danger" } else { "MODE/safe" }
        }
        Action::Access { admin, .. } => {
            if *admin { "ACCESS/maintenance" } else { "ACCESS/denied" }
        }
        Action::Route { primary, .. } => {
            if *primary { "ROUTE/skipped" } else { "ROUTE/primary" }
        }
        Action::Other => "OTHER",
    }
}

fn main() {
    let items = [
        ("A1", Action::Alert { urgent: false, acknowledged: false }),
        ("A2", Action::Alert { urgent: true, acknowledged: true }),
        ("B1", Action::Job { queued: true, interactive: true }),
        ("B2", Action::Job { queued: true, interactive: false }),
        ("C1", Action::Mode { safe: true, override_lock: false }),
        ("C2", Action::Mode { safe: true, override_lock: true }),
        ("D1", Action::Access { admin: true, maintenance: true }),
        ("D2", Action::Access { admin: true, maintenance: false }),
        ("E1", Action::Route { primary: true, disabled: false }),
        ("E2", Action::Route { primary: true, disabled: true }),
        ("F1", Action::Other),
    ];

    for (label, action) in items {
        println!("{} => {}", label, summarize(&action));
    }
}
