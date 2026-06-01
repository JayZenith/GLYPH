use std::collections::BTreeMap;

#[derive(Clone, Copy)]
enum Status {
    Open,
    InProgress,
    Resolved,
    Closed,
}

impl Status {
    fn as_str(&self) -> &'static str {
        match self {
            Status::Open => "Open",
            Status::InProgress => "InProgress",
            Status::Resolved => "Resolved",
            Status::Closed => "Closed",
        }
    }
}

enum Event<'a> {
    Create(&'a str),
    Start(&'a str),
    Resolve(&'a str),
    Reopen(&'a str),
    Close(&'a str),
}

fn main() {
    let events = [
        Event::Create("A"),
        Event::Start("A"),
        Event::Resolve("A"),
        Event::Create("B"),
        Event::Start("B"),
        Event::Reopen("B"),
        Event::Create("C"),
        Event::Resolve("C"),
        Event::Close("C"),
    ];

    let mut tickets: BTreeMap<&str, Status> = BTreeMap::new();

    for event in events {
        match event {
            Event::Create(id) => {
                tickets.insert(id, Status::Open);
            }
            Event::Start(id) => {
                tickets.insert(id, Status::Open);
            }
            Event::Resolve(id) => {
                tickets.insert(id, Status::Closed);
            }
            Event::Reopen(id) => {
                tickets.insert(id, Status::InProgress);
            }
            Event::Close(id) => {
                tickets.insert(id, Status::Resolved);
            }
        }
    }

    for (id, status) in tickets {
        println!("{}:{}", id, status.as_str());
    }
}
