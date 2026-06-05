enum Alert {
    Incident { code: u16, urgent: bool },
    Job { name: &'static str, retries: u8 },
    Audit { area: &'static str, privileged: bool },
    Info(&'static str),
}

fn summarize(alert: &Alert) -> (&'static str, &'static str, u8) {
    match alert {
        Alert::Incident { code, urgent } => {
            if *urgent {
                ("urgent", "incident", 0)
            } else if *code >= 500 {
                ("incident", "outage", 1)
            } else {
                ("incident", "latency", 2)
            }
        }
        Alert::Job { name, retries } => {
            if *retries > 0 {
                ("job", "retry", 6)
            } else {
                ("job", name, 8)
            }
        }
        Alert::Audit { area, privileged } => {
            if *privileged {
                ("audit", "privileged", 3)
            } else {
                ("audit", area, 11)
            }
        }
        Alert::Info(msg) => ("info", msg, 12),
    }
}

fn main() {
    let alerts = [
        Alert::Incident { code: 503, urgent: true },
        Alert::Incident { code: 503, urgent: false },
        Alert::Incident { code: 429, urgent: false },
        Alert::Job { name: "backup", retries: 1 },
        Alert::Job { name: "report", retries: 0 },
        Alert::Audit { area: "access", privileged: true },
        Alert::Audit { area: "config", privileged: false },
        Alert::Info("note"),
    ];

    let mut rows: Vec<String> = alerts
        .iter()
        .map(|a| {
            let (kind, label, prio) = summarize(a);
            format!("{} {} [prio={}]", kind, label, prio)
        })
        .collect();

    rows.sort_by_key(|line| {
        let start = line.find("[prio=").unwrap() + 6;
        let end = line[start..].find(']').unwrap() + start;
        line[start..end].parse::<u8>().unwrap()
    });

    print!("{}", rows.join("\n"));
}
