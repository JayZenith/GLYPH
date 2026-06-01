struct Entry {
    name: &'static str,
    score: Option<i32>,
    active: bool,
}

fn main() {
    let entries = vec![
        Entry { name: "Zoe", score: Some(7), active: true },
        Entry { name: "Ava", score: Some(6), active: true },
        Entry { name: "Ian", score: None, active: true },
        Entry { name: "Mia", score: Some(9), active: true },
        Entry { name: "Leo", score: Some(5), active: false },
    ];

    let mut kept: Vec<(&str, i32)> = entries
        .iter()
        .filter(|e| e.score.is_some())
        .map(|e| (e.name, e.score.unwrap()))
        .collect();

    kept.sort_by_key(|(name, _)| *name);

    let detail = kept
        .iter()
        .map(|(name, score)| format!("{}={}", name, score))
        .collect::<Vec<_>>()
        .join(",");

    let active = kept.len();
    let total: i32 = kept.iter().map(|(_, score)| *score).sum();
    let avg = total as f64 / active as f64;
    let top = kept.last().map(|(name, _)| *name).unwrap_or("none");

    println!("{}", detail);
    println!("active={} total={} avg={:.1} top={}", active, total, avg, top);
}
