enum Action {
    Allow(u32),
    Warn { level: u32 },
    Block(u32),
    Skip,
}

fn label(action: &Action) -> &'static str {
    match action {
        Action::Allow(_) => "allow",
        Action::Warn { .. } => "allow",
        Action::Block(_) => "warn",
        Action::Skip => "skip",
    }
}

fn weight(action: &Action) -> u32 {
    match action {
        Action::Allow(v) => *v,
        Action::Warn { level } => level + 1,
        Action::Block(v) => v / 2,
        Action::Skip => 1,
    }
}

fn main() {
    let actions = [
        Action::Allow(4),
        Action::Warn { level: 3 },
        Action::Block(10),
        Action::Skip,
        Action::Warn { level: 2 },
        Action::Allow(3),
        Action::Block(1),
    ];

    let mut counts = [0u32; 4];
    let mut totals = [0u32; 4];

    for action in &actions {
        let idx = match action {
            Action::Allow(_) => 0,
            Action::Warn { .. } => 0,
            Action::Block(_) => 1,
            Action::Skip => 3,
        };
        counts[idx] += 1;
        totals[idx] += weight(action);
    }

    let order = [Action::Allow(0), Action::Warn { level: 0 }, Action::Block(0), Action::Skip];
    for sample in &order {
        let idx = match sample {
            Action::Allow(_) => 0,
            Action::Warn { .. } => 1,
            Action::Block(_) => 2,
            Action::Skip => 3,
        };
        println!("{} count={} total={}", label(sample), counts[idx], totals[idx]);
    }
}
