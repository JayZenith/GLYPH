enum Task {
    Pending { urgent: bool, watchers: u8, batch: usize },
    Active { retries: u8, watchers: u8 },
    Closed { archived: bool, blocked: bool },
}

struct Item {
    name: &'static str,
    task: Task,
}

fn label(task: &Task) -> &'static str {
    match task {
        Task::Pending { urgent: true, .. } => "queue/urgent",
        Task::Pending { batch, .. } if *batch > 1 => "queue/bulk",
        Task::Pending { .. } => "queue/normal",
        Task::Active { retries, .. } if *retries > 0 => "run/retry",
        Task::Active { .. } => "run/ready",
        Task::Closed { blocked: true, .. } => "skip/blocked",
        Task::Closed { .. } => "done",
    }
}

fn main() {
    let items = [
        Item {
            name: "A",
            task: Task::Pending {
                urgent: true,
                watchers: 0,
                batch: 1,
            },
        },
        Item {
            name: "B",
            task: Task::Pending {
                urgent: false,
                watchers: 0,
                batch: 3,
            },
        },
        Item {
            name: "C",
            task: Task::Active {
                retries: 2,
                watchers: 0,
            },
        },
        Item {
            name: "D",
            task: Task::Active {
                retries: 0,
                watchers: 0,
            },
        },
        Item {
            name: "E",
            task: Task::Closed {
                archived: false,
                blocked: true,
            },
        },
        Item {
            name: "F",
            task: Task::Closed {
                archived: true,
                blocked: false,
            },
        },
        Item {
            name: "G",
            task: Task::Pending {
                urgent: false,
                watchers: 2,
                batch: 2,
            },
        },
        Item {
            name: "H",
            task: Task::Active {
                retries: 0,
                watchers: 1,
            },
        },
    ];

    let out = items
        .iter()
        .map(|item| format!("{}:{}", item.name, label(&item.task)))
        .collect::<Vec<_>>()
        .join("\n");

    println!("{}", out);
}
