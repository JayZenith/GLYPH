struct Item {
    name: &'static str,
    active: bool,
    score: &'static str,
    tags: &'static [&'static str],
}

fn main() {
    let items = vec![
        Item { name: "alpha", active: true, score: "10", tags: &["core", "fast"] },
        Item { name: "beta", active: true, score: "8", tags: &["fast"] },
        Item { name: "gamma", active: false, score: "7", tags: &["core"] },
        Item { name: "delta", active: true, score: "x", tags: &["core", "slow"] },
        Item { name: "epsilon", active: true, score: "5", tags: &["slow"] },
    ];

    let rows: Vec<(String, i32)> = items
        .iter()
        .filter(|item| item.active || item.tags.iter().any(|t| *t == "core"))
        .filter_map(|item| item.score.parse::<i32>().ok().map(|score| (item.name.to_string(), score)))
        .collect();

    let total: i32 = rows.iter().map(|(_, score)| *score).sum();

    for (name, score) in &rows {
        println!("{}:{}", name, score);
    }
    println!("SUM={}", total);
}
