enum Action {
    Sync,
    Cleanup,
    Backup,
    Export,
    Notify,
    Report,
}

struct Job {
    action: Action,
    urgent: bool,
    blocked: bool,
    manual: bool,
    retries: u8,
    label: &'static str,
}

fn action_name(action: &Action) -> &'static str {
    match action {
        Action::Sync => "sync",
        Action::Cleanup => "cleanup",
        Action::Backup => "backup",
        Action::Export => "export",
        Action::Notify => "notify",
        Action::Report => "report",
    }
}

fn summarize(job: &Job) -> String {
    let state = match job.action {
        Action::Backup | Action::Notify if job.retries > 0 => "retrying",
        Action::Cleanup if job.manual => "manual-cleanup",
        Action::Export | Action::Report if job.urgent => "active-high",
        Action::Sync => "active-low",
        _ if job.blocked => "blocked",
        _ => "pending-low",
    };

    let mut extras = Vec::new();
    if job.manual {
        extras.push("manual");
    }
    if job.retries > 0 {
        extras.push("retry");
    }

    if extras.is_empty() {
        format!("{} => {}: {}", action_name(&job.action), state, job.label)
    } else {
        format!(
            "{} => {}: {} [{}]",
            action_name(&job.action),
            state,
            job.label,
            extras.join(",")
        )
    }
}

fn main() {
    let jobs = [
        Job {
            action: Action::Backup,
            urgent: true,
            blocked: true,
            manual: false,
            retries: 2,
            label: "db-backup",
        },
        Job {
            action: Action::Sync,
            urgent: false,
            blocked: false,
            manual: false,
            retries: 0,
            label: "edge-sync",
        },
        Job {
            action: Action::Cleanup,
            urgent: false,
            blocked: true,
            manual: true,
            retries: 0,
            label: "cache-clean",
        },
        Job {
            action: Action::Export,
            urgent: true,
            blocked: false,
            manual: true,
            retries: 0,
            label: "weekly-export",
        },
        Job {
            action: Action::Notify,
            urgent: false,
            blocked: true,
            manual: false,
            retries: 1,
            label: "email-blast",
        },
        Job {
            action: Action::Report,
            urgent: true,
            blocked: false,
            manual: true,
            retries: 0,
            label: "monthly-report",
        },
    ];

    for job in jobs {
        println!("{}", summarize(&job));
    }
}
