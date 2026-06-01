use std::cmp::Ordering;
use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Task {
    id: u32,
    name: &'static str,
    points: u32,
    deadline: u32,
}

fn main() {
    let tasks = vec![
        Task { id: 1, name: "alpha", points: 10, deadline: 2 },
        Task { id: 2, name: "beta", points: 10, deadline: 2 },
        Task { id: 3, name: "gamma", points: 10, deadline: 3 },
        Task { id: 4, name: "delta", points: 9, deadline: 1 },
        Task { id: 5, name: "zeta", points: 9, deadline: 4 },
        Task { id: 1, name: "alpha", points: 8, deadline: 5 },
        Task { id: 2, name: "beta", points: 7, deadline: 6 },
    ];

    let mut best: HashMap<u32, Task> = HashMap::new();
    for task in tasks {
        best.insert(task.id, task);
    }

    let mut items: Vec<Task> = best.into_values().collect();
    items.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then_with(|| a.deadline.cmp(&b.deadline))
            .then_with(|| {
                if a.name.len() == b.name.len() {
                    Ordering::Equal
                } else {
                    a.name.len().cmp(&b.name.len())
                }
            })
    });

    for (i, task) in items.iter().enumerate() {
        println!("{}. {} [{} pts, due {}]", i + 1, task.name, task.points, task.deadline);
    }
}
