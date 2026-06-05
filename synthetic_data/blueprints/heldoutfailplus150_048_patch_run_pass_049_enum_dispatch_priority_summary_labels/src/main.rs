enum Event {
    Login { user: &'static str, failed_attempts: u8, tagged: bool },
    Payment { user: &'static str, retried: bool, flagged: bool },
    Shipment { user: &'static str, delayed_days: u8, international: bool },
    Note { user: &'static str, kind: NoteKind },
}

enum NoteKind {
    Profile,
    Billing,
    Security,
}

fn summarize(event: &Event) -> String {
    match event {
        Event::Login { user, failed_attempts, .. } if *failed_attempts >= 3 => {
            format!("{} => WARN:login-retries", user)
        }
        Event::Login { user, .. } => format!("{} => INFO:login", user),
        Event::Payment { user, flagged, .. } if *flagged => {
            format!("{} => ALERT:payment-review", user)
        }
        Event::Payment { user, .. } => format!("{} => INFO:payment", user),
        Event::Shipment { user, delayed_days, .. } if *delayed_days > 0 => {
            format!("{} => WARN:shipment-delay", user)
        }
        Event::Shipment { user, .. } => format!("{} => INFO:shipment", user),
        Event::Note { user, kind } => match kind {
            NoteKind::Security => format!("{} => WARN:security-note", user),
            NoteKind::Billing => format!("{} => INFO:billing-note", user),
            NoteKind::Profile => format!("{} => INFO:profile-note", user),
        },
    }
}

fn main() {
    let events = vec![
        Event::Login {
            user: "u1",
            failed_attempts: 4,
            tagged: true,
        },
        Event::Payment {
            user: "u2",
            retried: true,
            flagged: true,
        },
        Event::Note {
            user: "u3",
            kind: NoteKind::Billing,
        },
        Event::Shipment {
            user: "u4",
            delayed_days: 2,
            international: true,
        },
        Event::Note {
            user: "u5",
            kind: NoteKind::Security,
        },
        Event::Note {
            user: "u6",
            kind: NoteKind::Profile,
        },
    ];

    let out = events.iter().map(summarize).collect::<Vec<_>>().join("\n");
    println!("{}", out);
}
