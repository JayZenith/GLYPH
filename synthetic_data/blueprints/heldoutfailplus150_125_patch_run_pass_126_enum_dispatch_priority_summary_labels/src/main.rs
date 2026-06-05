enum Alert {
    Ping { urgent: bool, customer_visible: bool },
    Deploy { blocked: bool, dry_run: bool },
    Sync { retries: u8, stale: bool },
    Quota { used_pct: u8 },
}

fn render(alert: &Alert) -> (&'static str, String) {
    match alert {
        Alert::Ping { urgent, .. } => {
            if *urgent {
                ("warning", "check soon".to_string())
            } else {
                ("defer", "can wait".to_string())
            }
        }
        Alert::Deploy { dry_run, blocked } => {
            if *dry_run {
                ("ok", "dry-run only".to_string())
            } else if *blocked {
                ("warning", "rollout blocked".to_string())
            } else {
                ("ok", "deploying".to_string())
            }
        }
        Alert::Sync { retries, stale } => {
            if *stale {
                ("warning", format!("stale after {} retries", retries))
            } else {
                ("ok", "normal background sync".to_string())
            }
        }
        Alert::Quota { used_pct } => {
            if *used_pct >= 90 {
                ("critical", format!("usage at {}%", used_pct))
            } else {
                ("ok", format!("usage at {}%", used_pct))
            }
        }
    }
}

fn kind(alert: &Alert) -> &'static str {
    match alert {
        Alert::Ping { .. } => "ping",
        Alert::Deploy { .. } => "deploy",
        Alert::Sync { .. } => "sync",
        Alert::Quota { .. } => "quota",
    }
}

fn main() {
    let alerts = vec![
        Alert::Ping { urgent: false, customer_visible: false },
        Alert::Deploy { blocked: true, dry_run: false },
        Alert::Sync { retries: 3, stale: true },
        Alert::Quota { used_pct: 80 },
        Alert::Ping { urgent: true, customer_visible: true },
        Alert::Sync { retries: 0, stale: false },
        Alert::Deploy { blocked: true, dry_run: true },
    ];

    let mut critical = 0;
    let mut warning = 0;
    let mut audit = 0;
    let mut defer = 0;
    let mut ok = 0;

    for (idx, alert) in alerts.iter().enumerate() {
        let (label, note) = render(alert);
        match label {
            "critical" => critical += 1,
            "warning" => warning += 1,
            "audit" => audit += 1,
            "defer" => defer += 1,
            "ok" => ok += 1,
            _ => {}
        }
        println!("{}. {} [{}]: {}", idx + 1, kind(alert), label, note);
    }

    println!(
        "summary critical={} warning={} audit={} defer={} ok={}",
        critical, warning, audit, defer, ok
    );
}
