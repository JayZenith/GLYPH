use std::collections::BTreeMap;

struct Record {
    active: bool,
    tags: &'static [&'static str],
}

fn main() {
    let records = vec![
        Record {
            active: true,
            tags: &["rust", " cli", "db"],
        },
        Record {
            active: false,
            tags: &["rust", "ops"],
        },
        Record {
            active: true,
            tags: &["API", "rust", ""],
        },
        Record {
            active: true,
            tags: &["tools", "db ", "CLI"],
        },
        Record {
            active: true,
            tags: &["tools", "  rust  "],
        },
    ];

    let mut counts = BTreeMap::new();

    for tag in records
        .iter()
        .flat_map(|record| record.tags.iter())
        .map(|tag| *tag)
    {
        *counts.entry(tag.to_string()).or_insert(0usize) += 1;
    }

    let mut items: Vec<_> = counts.into_iter().collect();
    items.sort_by(|a, b| a.0.cmp(&b.0));

    let output = items
        .into_iter()
        .map(|(tag, count)| format!("{}: {}", tag, count))
        .collect::<Vec<_>>()
        .join("\n");

    println!("{}", output);
}
