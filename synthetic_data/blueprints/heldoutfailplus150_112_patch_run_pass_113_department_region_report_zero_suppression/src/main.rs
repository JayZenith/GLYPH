use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    region: &'static str,
    dept: &'static str,
    amount: i32,
    active: bool,
}

fn main() {
    let rows = [
        Row { region: "North", dept: "Sales", amount: 10, active: true },
        Row { region: "North", dept: "Sales", amount: 4, active: true },
        Row { region: "North", dept: "Support", amount: 3, active: true },
        Row { region: "North", dept: "Ops", amount: 0, active: true },
        Row { region: "South", dept: "Sales", amount: 0, active: true },
        Row { region: "South", dept: "Support", amount: 2, active: true },
        Row { region: "South", dept: "Support", amount: 3, active: true },
        Row { region: "South", dept: "Ops", amount: 1, active: false },
        Row { region: "East", dept: "Sales", amount: 2, active: true },
        Row { region: "East", dept: "Sales", amount: 7, active: true },
        Row { region: "East", dept: "Support", amount: 2, active: true },
        Row { region: "East", dept: "Ops", amount: 0, active: true },
        Row { region: "West", dept: "Ops", amount: 0, active: true },
        Row { region: "West", dept: "Sales", amount: 5, active: false },
    ];

    let mut groups: BTreeMap<&str, BTreeMap<&str, (usize, i32)>> = BTreeMap::new();
    let mut grand_count = 0usize;
    let mut grand_total = 0i32;

    for r in rows {
        let entry = groups.entry(r.region).or_default().entry(r.dept).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += r.amount;
        grand_count += 1;
        grand_total += r.amount;
    }

    let mut out = String::new();
    out.push_str("Active department report\n");
    for (region, depts) in groups {
        out.push_str(&format!("Region {}\n", region));
        for (dept, (count, total)) in depts {
            out.push_str(&format!("- {}: count={}, total={}\n", dept, count, total));
        }
    }
    out.push_str(&format!("Grand total: count={}, total={}", grand_count, grand_total));
    print!("{}", out);
}
