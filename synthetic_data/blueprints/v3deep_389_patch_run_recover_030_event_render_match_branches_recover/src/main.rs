enum Event {
    Login { user: &'static str, via: &'static str, ok: bool },
    Transfer { from: &'static str, to: &'static str, amount: u32, urgent: bool, retry: bool },
    Logout { user: &'static str, reason: Reason },
}

enum Reason {
    Idle,
    Timeout,
}

fn render(e: &Event) -> String {
    match e {
        Event::Login { user, via, ok } => {
            let status = if *ok { "failed: denied" } else { "ok" };
            format!("LOGIN {} [{}] {}", user, via, status)
        }
        Event::Transfer { from, to, amount, urgent, retry } => {
            let tag = if *urgent {
                " retry"
            } else if *retry {
                " urgent"
            } else {
                ""
            };
            format!("TRANSFER {} -> {} ${}{}", to, from, amount, tag)
        }
        Event::Logout { user, reason } => {
            let reason = match reason {
                Reason::Idle => "timeout",
                Reason::Timeout => "idle",
            };
            format!("LOGOUT {} {}", user, reason)
        }
    }
}

fn main() {
    let events = [
        Event::Login { user: "alice", via: "web", ok: true },
        Event::Login { user: "bob", via: "api", ok: false },
        Event::Transfer { from: "payroll", to: "ops", amount: 1250, urgent: true, retry: false },
        Event::Transfer { from: "reserve", to: "tax", amount: 300, urgent: false, retry: true },
        Event::Logout { user: "alice", reason: Reason::Idle },
        Event::Logout { user: "bob", reason: Reason::Timeout },
    ];

    for event in events.iter() {
        println!("{}", render(event));
    }
}
