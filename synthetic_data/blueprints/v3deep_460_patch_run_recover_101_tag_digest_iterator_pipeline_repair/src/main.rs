struct Item {
    owner: &'static str,
    active: bool,
    score: i32,
    tags: &'static [&'static str],
}

fn main() {
    let items = vec![
        Item { owner: "amy", active: true, score: 7, tags: &["red", "hot", "red"] },
        Item { owner: "bob", active: true, score: 5, tags: &["blue", "new"] },
        Item { owner: "amy", active: false, score: 8, tags: &["hot", "new"] },
        Item { owner: "eve", active: true, score: 4, tags: &["new", "red"] },
        Item { owner: "bob", active: true, score: 9, tags: &["hot", "fast"] },
        Item { owner: "zoe", active: true, score: 2, tags: &["red", "old"] },
    ];

    let active_count = items.iter().filter(|it| it.active && it.score >= 5).count();

    let mut tags: Vec<&str> = items
        .iter()
        .filter(|it| it.active)
        .flat_map(|it| it.tags.iter().copied())
        .filter(|tag| tag.len() >= 3)
        .collect();
    tags.sort();

    let mut owners: Vec<&str> = items
        .iter()
        .filter(|it| it.active && it.score > 5)
        .map(|it| it.owner)
        .collect();
    owners.sort();

    println!("active={}", active_count);
    println!("tags={}", tags.join("|"));
    println!("owners={}", owners.join(","));
}
