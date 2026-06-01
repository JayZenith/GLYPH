enum Event {
    SignIn { user: &'static str },
    Upload { name: &'static str, bytes: u64 },
    Delete { target: &'static str },
    StartJob { job: &'static str },
    Config { scope: &'static str, key: &'static str, value: &'static str },
    Unknown,
}

#[derive(Default)]
struct Stats {
    signin: u32,
    upload_bytes: u64,
    started: u32,
    deleted: u32,
    config: u32,
    unknown: u32,
}

fn render_event(event: &Event, stats: &mut Stats) -> String {
    match event {
        Event::SignIn { user } => {
            stats.signin += 1;
            format!("{}: signed in", user)
        }
        Event::Upload { name, bytes } => {
            stats.upload_bytes += 1;
            format!("{}: uploaded", name)
        }
        Event::Delete { target } => {
            stats.deleted += 1;
            format!("{} deleted", target)
        }
        Event::StartJob { job } => {
            stats.started += 1;
            format!("{}: queued", job)
        }
        Event::Config { scope, key, value } => {
            stats.config += 1;
            format!("{}: config {}:{}", scope, key, value)
        }
        Event::Unknown => {
            stats.deleted += 1;
            "audit: skipped".to_string()
        }
    }
}

fn summary(stats: &Stats) -> String {
    format!(
        "summary signin={} upload_bytes={} started={} deleted={} config={} unknown={}",
        stats.signin,
        stats.upload_bytes,
        stats.started,
        stats.deleted,
        stats.config,
        stats.unknown
    )
}

fn main() {
    let events = [
        Event::SignIn { user: "alice" },
        Event::Upload {
            name: "build.log",
            bytes: 2048,
        },
        Event::StartJob { job: "deploy" },
        Event::Delete { target: "cache" },
        Event::Config {
            scope: "prod",
            key: "timeout",
            value: "30",
        },
        Event::Unknown,
    ];

    let mut stats = Stats::default();
    let mut lines = Vec::new();
    for event in &events {
        lines.push(render_event(event, &mut stats));
    }
    lines.push(summary(&stats));
    print!("{}", lines.join("\n"));
}
