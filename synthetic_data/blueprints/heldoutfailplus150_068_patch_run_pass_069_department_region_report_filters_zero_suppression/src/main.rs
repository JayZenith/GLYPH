use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy)]
struct Record {
    dept: &'static str,
    region: &'static str,
    count: i32,
    active: bool,
    include: bool,
}

fn records() -> Vec<Record> {
    vec![
        Record { dept: "Sales", region: "NA", count: 10, active: true, include: true },
        Record { dept: "Sales", region: "EU", count: 7, active: true, include: true },
        Record { dept: "Sales", region: "APAC", count: 0, active: false, include: true },
        Record { dept: "Support", region: "EU", count: 9, active: true, include: true },
        Record { dept: "Support", region: "NA", count: 5, active: true, include: true },
        Record { dept: "Support", region: "APAC", count: 0, active: false, include: true },
        Record { dept: "Engineering", region: "APAC", count: 8, active: true, include: true },
        Record { dept: "Engineering", region: "EU", count: 0, active: false, include: true },
        Record { dept: "HR", region: "NA", count: 0, active: true, include: true },
        Record { dept: "Legal", region: "EU", count: 4, active: true, include: false },
        Record { dept: "Ops", region: "NA", count: -3, active: true, include: true },
    ]
}

fn build_report(rows: &[Record]) -> String {
    let mut grouped: BTreeMap<&str, Vec<Record>> = BTreeMap::new();
    for r in rows {
        if r.include {
            grouped.entry(r.dept).or_default().push(*r);
        }
    }

    let mut lines = vec!["DEPARTMENT REPORT".to_string()];
    let mut grand_total = 0;
    let mut grand_active = 0;

    for (dept, items) in grouped {
        let total: i32 = items.iter().map(|r| r.count).sum();
        let active = items.iter().filter(|r| r.active).count();
        grand_total += total;
        grand_active += active;

        let mut seen = BTreeSet::new();
        let mut regions = Vec::new();
        for r in &items {
            if seen.insert(r.region) {
                regions.push(format!("{}:{}", r.region, r.count));
            }
        }

        lines.push(format!("{} | total={} | active={} | regions={}", dept, total, active, regions.join(",")));
    }

    lines.push(format!("TOTAL | total={} | active={}", grand_total, grand_active));
    lines.join("\n")
}

fn main() {
    println!("{}", build_report(&records()));
}
