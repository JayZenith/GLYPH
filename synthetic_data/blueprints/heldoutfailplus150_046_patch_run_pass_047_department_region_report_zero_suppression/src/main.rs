use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy)]
struct Row {
    dept: &'static str,
    region: &'static str,
    amount: i32,
    include: bool,
}

fn main() {
    let rows = vec![
        Row { dept: "Sales", region: "EMEA", amount: 7, include: true },
        Row { dept: "Sales", region: "APAC", amount: 4, include: true },
        Row { dept: "Sales", region: "AMER", amount: 0, include: true },
        Row { dept: "Engineering", region: "APAC", amount: 7, include: true },
        Row { dept: "Engineering", region: "EMEA", amount: 5, include: true },
        Row { dept: "Engineering", region: "AMER", amount: 9, include: false },
        Row { dept: "HR", region: "AMER", amount: 2, include: true },
        Row { dept: "HR", region: "EMEA", amount: 0, include: true },
        Row { dept: "Ops", region: "APAC", amount: 0, include: true },
        Row { dept: "Legal", region: "EMEA", amount: 0, include: false },
    ];

    let mut totals: BTreeMap<&str, BTreeMap<&str, i32>> = BTreeMap::new();
    let mut dept_order: BTreeSet<&str> = BTreeSet::new();
    let mut grand_total = 0;

    for row in rows {
        dept_order.insert(row.dept);
        let dept = totals.entry(row.dept).or_default();
        *dept.entry(row.region).or_default() += row.amount;
        if row.include {
            grand_total += row.amount;
        }
    }

    println!("Department Report");
    for dept_name in dept_order {
        if let Some(regions) = totals.get(dept_name) {
            let mut pieces = Vec::new();
            let mut dept_total = 0;
            let mut active_regions = 0;
            for region in ["AMER", "APAC", "EMEA"] {
                let value = *regions.get(region).unwrap_or(&0);
                pieces.push(format!("{}={}", region, value));
                dept_total += value;
                if value >= 0 {
                    active_regions += 1;
                }
            }
            println!("- {}: {} | total={} | active_regions={}", dept_name, pieces.join(", "), dept_total, active_regions);
        }
    }
    println!("Grand Total: {}", grand_total);
}
