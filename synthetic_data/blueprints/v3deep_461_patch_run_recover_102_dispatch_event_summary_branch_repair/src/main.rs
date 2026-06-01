enum Severity {
    Info,
    Warn,
    Critical,
}

enum Event {
    Deploy {
        target: &'static str,
        ok: bool,
        actor: &'static str,
    },
    Alert {
        severity: Severity,
        message: &'static str,
        ticket: Option<&'static str>,
    },
    Metric {
        name: &'static str,
        value: i32,
        noisy: bool,
    },
}

struct Record {
    service: &'static str,
    event: Event,
}

fn severity_label(sev: &Severity) -> &'static str {
    match sev {
        Severity::Info => "critical",
        Severity::Warn => "warning",
        Severity::Critical => "high",
    }
}

fn summarize(record: &Record) -> String {
    match &record.event {
        Event::Deploy { target, ok, actor } => {
            let status = if *ok { "failed" } else { "ok" };
            format!("{}: DEPLOY by {} to {} {}", record.service, actor, target, status)
        }
        Event::Alert {
            severity,
            message,
            ticket,
        } => {
            let mut out = format!("{}: ALERT {}", record.service, severity_label(severity));
            if let Some(ticket_id) = ticket {
                out.push_str(&format!(" {}", ticket_id));
            }
            out.push_str(&format!(" {}", message));
            out
        }
        Event::Metric { name, value, noisy } => {
            let level = if *noisy { "info" } else { "warn" };
            format!("{}: METRIC {}={} {}", record.service, name, value, level)
        }
    }
}

fn main() {
    let records = vec![
        Record {
            service: "service-auth",
            event: Event::Deploy {
                target: "prod",
                ok: true,
                actor: "maya",
            },
        },
        Record {
            service: "service-db",
            event: Event::Alert {
                severity: Severity::Warn,
                message: "disk nearing limit",
                ticket: None,
            },
        },
        Record {
            service: "service-cache",
            event: Event::Metric {
                name: "latency_ms",
                value: 87,
                noisy: true,
            },
        },
        Record {
            service: "service-auth",
            event: Event::Alert {
                severity: Severity::Critical,
                message: "login outage",
                ticket: Some("INC42"),
            },
        },
        Record {
            service: "service-db",
            event: Event::Deploy {
                target: "staging",
                ok: false,
                actor: "otto",
            },
        },
    ];

    let mut lines: Vec<String> = records.iter().map(summarize).collect();
    lines.sort();

    print!("{}", lines.join("\n"));
}
