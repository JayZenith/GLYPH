use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Entry {
    category: &'static str,
    amount: i32,
}

fn main() {
    let entries = [
        Entry { category: "food", amount: 25 },
        Entry { category: "travel", amount: 120 },
        Entry { category: "food", amount: -5 },
        Entry { category: "books", amount: 30 },
        Entry { category: "travel", amount: 90 },
        Entry { category: "office", amount: 15 },
        Entry { category: "food", amount: 10 },
    ];

    let mut totals: BTreeMap<&str, i32> = BTreeMap::new();
    for entry in entries {
        *totals.entry(entry.category).or_insert(0) += entry.amount;
    }

    let mut rows: Vec<_> = totals.into_iter().collect();
    rows.sort_by(|a, b| a.0.cmp(b.0));

    println!("Expenses by category");
    let mut grand_total = 0;
    for (category, total) in rows {
        grand_total += total;
        println!("{} = {}", category, total);
    }
    println!("grand total: {}", grand_total);
}
