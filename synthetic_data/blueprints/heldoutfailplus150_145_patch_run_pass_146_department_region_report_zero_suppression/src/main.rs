use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy)]
struct Record {
    region: &'static str,
    dept: &'static str,
    amount: i32,
    active: bool,
}

fn main() {
    let rows = [
        Record { region: "North", dept: "Sales", amount: 100, active: true },
        Record { region: "North", dept: "Support", amount: 0, active: true },
        Record { region: "North", dept: "Ops", amount: 40, active: false },
        Record { region: "South", dept: "Sales", amount: 0, active: true },
        Record { region: "South", dept: "Support", amount: 10, active: false },
        Record { region: "East", dept: "Sales", amount: 70, active: true },
        Record { region: "East", dept: "Sales", amount: 60, active: true },
        Record { region: "East", dept: "Ops", amount: 90, active: true },
        Record { region: "West", dept: "Ops", amount: 55, active: true },
        Record { region: "West", dept: "Ops", amount: 75, active: true },
        Record { region: "West", dept: "Support", amount: 0, active: true },
    ];

    let regions = ["North", "South", "East", "West"];
    let depts = ["Sales", "Support", "Ops"];

    print!(build_report(&rows, &regions, &depts, 0));
}

fn build_report(rows: &[Record], regions: &[&str], depts: &[&str], min_amount: i32) -> String {
    let mut dept_totals: BTreeMap<&str, BTreeMap<&str, (usize, i32)>> = BTreeMap::new();
    let mut region_totals: BTreeMap<&str, (usize, i32)> = BTreeMap::new();
    let region_set: BTreeSet<&str> = regions.iter().copied().collect();

    for row in rows {
        if !row.active || row.amount < min_amount || !region_set.contains(row.region) {
            continue;
        }
        let e = dept_totals
            .entry(row.region)
            .or_default()
            .entry(row.dept)
            .or_insert((0, 0));
        e.0 += 1;
        e.1 += row.amount;

        let r = region_totals.entry(row.region).or_insert((0, 0));
        r.0 += 1;
        r.1 += row.amount;
    }

    let mut out = String::from("SALES REPORT\n");
    for region in region_totals.keys() {
        let (count, amount) = region_totals.get(region).copied().unwrap_or((0, 0));
        out.push_str(&format!("Region {}: count={} amount={}\n", region, count, amount));

        if let Some(dm) = dept_totals.get(region) {
            for dept in depts {
                let (dc, da) = dm.get(dept).copied().unwrap_or((0, 0));
                out.push_str(&format!("  {}: count={} amount={}\n", dept, dc, da));
            }
        }
    }

    if out.ends_with('\n') {
        out.pop();
    }
    out
}
