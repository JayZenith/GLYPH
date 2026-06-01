enum Action {
    Sync { target: &'static str, urgent: bool },
    Remove { item: &'static str, dry_run: bool },
    Archive { item: &'static str, days: u32 },
    Skip { item: &'static str, enabled: bool },
}

fn describe(action: &Action) -> String {
    match action {
        Action::Sync { target, urgent } => {
            let speed = if *urgent { "soon" } else { "later" };
            format!("sync {} {}", target, speed)
        }
        Action::Remove { item, dry_run } => {
            let mode = if *dry_run { "[live]" } else { "[dry-run]" };
            format!("remove {} {}", item, mode)
        }
        Action::Archive { item, days } => format!("archive {} after {}h", item, days),
        Action::Skip { item, enabled } => {
            let state = if *enabled { "disabled" } else { "enabled" };
            format!("skip {} ({})", item, state)
        }
    }
}

fn main() {
    let actions = [
        Action::Sync {
            target: "local",
            urgent: true,
        },
        Action::Skip {
            item: "remote",
            enabled: false,
        },
        Action::Remove {
            item: "cache",
            dry_run: true,
        },
        Action::Archive {
            item: "logs",
            days: 7,
        },
    ];

    for action in actions.iter() {
        println!("{}", describe(action));
    }
}
