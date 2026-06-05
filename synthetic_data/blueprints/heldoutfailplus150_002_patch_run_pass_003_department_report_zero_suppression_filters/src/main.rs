use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Record {
    region: &'static str,
    dept: &'static str,
    kind: &'static str,
    amount: i32,
    active: bool,
}

fn data() -> Vec<Record> {
    vec![
        Record { region: "North", dept: "Sales", kind: "sale", amount: 5, active: true },
        Record { region: "North", dept: "Sales", kind: "return", amount: 1, active: true },
        Record { region: "North", dept: "HR", kind: "sale", amount: 4, active: true },
        Record { region: "North", dept: "HR", kind: "return", amount: 2, active: true },
        Record { region: "South", dept: "Sales", kind: "sale", amount: 1, active: true },
        Record { region: "South", dept: "HR", kind: "sale", amount: 0, active: true },
        Record { region: "East", dept: "Support", kind: "sale", amount: 5, active: true },
        Record { region: "East", dept: "Support", kind: "return", amount: 1, active: true },
        Record { region: "East", dept: "Sales", kind: "sale", amount: 0, active: true },
        Record { region: "West", dept: "HR", kind: "sale", amount: 3, active: true },
        Record { region: "West", dept: "Sales", kind: "sale", amount: 2, active: true },
        Record { region: "Central", dept: "Sales", kind: "sale", amount: 9, active: false },
        Record { region: "Central", dept: "Support", kind: "return", amount: 1, active: false },
        Record { region: "East", dept: "HR", kind: "return", amount: 2, active: true },
        Record { region: "South", dept: "Support", kind: "return", amount: 1, active: true },
    ]
}

fn main() {
    let rows = data();
    let mut groups: BTreeMap<(&str, &str), (i32, i32)> = BTreeMap::new();

    for r in rows {
        let entry = groups.entry((r.region, r.dept)).or_insert((0, 0));
        if r.kind == "sale" {
            entry.0 += r.amount;
        } else {
            entry.1 += r.amount;
        }
    }

    println!("Department Report");

    let mut region_totals: BTreeMap<&str, i32> = BTreeMap::new();
    for ((region, dept), (sales, returns)) in &groups {
        let net = sales + returns;
        println!("{} | {} | net={} | sales={} | returns={}", region, dept, net, sales, returns);
        *region_totals.entry(region).or_insert(0) += net;
    }

    println!("-- region totals --");
    for (region, total) in region_totals {
        println!("{} => {}", region, total);
    }
}
