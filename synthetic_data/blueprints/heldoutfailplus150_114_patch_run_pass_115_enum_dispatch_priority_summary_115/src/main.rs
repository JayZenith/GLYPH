enum Priority {
    Low,
    Normal,
    High,
    Critical,
}

enum Task {
    Deploy { service: &'static str, canary: bool },
    Audit { actor: &'static str, urgent: bool },
    Restart { target: &'static str, force: bool },
    Cleanup { target: &'static str, deep: bool },
}

struct Entry {
    priority: Priority,
    task: Task,
}

fn summarize(entry: &Entry) -> String {
    let level = match entry.priority {
        Priority::Critical => "critical",
        Priority::High => "high",
        Priority::Normal => "normal",
        Priority::Low => "low",
    };

    let detail = match &entry.task {
        Task::Deploy { service, .. } => format!("deploy [{}]", service),
        Task::Audit { actor, urgent } => {
            if *urgent {
                format!("audit [{}|override]", actor)
            } else {
                format!("audit [{}]", actor)
            }
        }
        Task::Restart { target, force } => {
            if *force {
                format!("restart [{}|force]", target)
            } else {
                format!("restart [{}]", target)
            }
        }
        Task::Cleanup { target, deep } => {
            if *deep {
                format!("cleanup [{}|deep]", target)
            } else {
                format!("cleanup [{}]", target)
            }
        }
    };

    let action = match (&entry.priority, &entry.task) {
        (Priority::Critical, Task::Restart { .. }) => "queue",
        (Priority::Critical, Task::Audit { urgent: true, .. }) => "ALERT",
        (Priority::High, _) => "queue",
        (_, Task::Cleanup { .. }) => "skip",
        (Priority::Low, _) => "note",
        _ => "note",
    };

    format!("{} => {} {}", level, action, detail)
}

fn main() {
    let entries = [
        Entry {
            priority: Priority::Critical,
            task: Task::Audit {
                actor: "alice",
                urgent: true,
            },
        },
        Entry {
            priority: Priority::Critical,
            task: Task::Restart {
                target: "db",
                force: false,
            },
        },
        Entry {
            priority: Priority::High,
            task: Task::Deploy {
                service: "api",
                canary: true,
            },
        },
        Entry {
            priority: Priority::High,
            task: Task::Audit {
                actor: "bob",
                urgent: false,
            },
        },
        Entry {
            priority: Priority::Normal,
            task: Task::Deploy {
                service: "web",
                canary: false,
            },
        },
        Entry {
            priority: Priority::Normal,
            task: Task::Cleanup {
                target: "cache",
                deep: true,
            },
        },
        Entry {
            priority: Priority::Low,
            task: Task::Audit {
                actor: "carol",
                urgent: false,
            },
        },
    ];

    for (i, entry) in entries.iter().enumerate() {
        if i > 0 {
            println!();
        }
        print!("{}", summarize(entry));
    }
}
