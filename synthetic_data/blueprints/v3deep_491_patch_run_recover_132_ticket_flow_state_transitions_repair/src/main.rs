use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Status {
    New,
    InProgress,
    Blocked,
    Closed,
}

enum Event {
    Create(&'static str),
    Start(&'static str),
    Block(&'static str),
    Resume(&'static str),
    Close(&'static str),
}

fn main() {
    let events = [
        Event::Create("T1"),
        Event::Start("T1"),
        Event::Close("T1"),
        Event::Create("T2"),
        Event::Start("T2"),
        Event::Block("T2"),
        Event::Resume("T2"),
        Event::Create("T3"),
    ];

    let mut tickets: BTreeMap<&str, Status> = BTreeMap::new();

    for event in events {
        match event {
            Event::Create(id) => {
                tickets.insert(id, Status::InProgress);
            }
            Event::Start(id) => {
                tickets.insert(id, Status::InProgress);
            }
            Event::Block(id) => {
                tickets.insert(id, Status::Blocked);
            }
            Event::Resume(id) => {
                tickets.insert(id, Status::New);
            }
            Event::Close(id) => {
                tickets.insert(id, Status::Blocked);
            }
        }
    }

    for (id, status) in tickets {
        let label = match status {
            Status::New => "new",
            Status::InProgress => "working",
            Status::Blocked => "blocked",
            Status::Closed => "closed",
        };
        println!("{}={}", id, label);
    }
}
