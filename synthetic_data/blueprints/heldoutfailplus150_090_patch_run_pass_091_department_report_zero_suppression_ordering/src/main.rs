use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Entry {
    region: &'static str,
    dept: &'static str,
    hours: i32,
    active: bool,
}

fn build_report(entries: &[Entry]) -> String {
    let mut by_region: BTreeMap<&str, BTreeMap<&str, i32>> = BTreeMap::new();
    let mut counts: BTreeMap<&str, usize> = BTreeMap::new();
    let mut totals: BTreeMap<&str, i32> = BTreeMap::new();

    for e in entries {
        if !e.active && e.hours == 0 {
            continue;
        }
        *by_region.entry(e.region).or_default().entry(e.dept).or_default() += e.hours;
        *counts.entry(e.region).or_default() += 1;
        *totals.entry(e.region).or_default() += e.hours;
    }

    let mut out = String::from("Department Report\n");
    let mut grand_count = 0usize;
    let mut grand_hours = 0i32;

    for (region, depts) in by_region {
        let count = counts.get(region).copied().unwrap_or(0);
        let total = totals.get(region).copied().unwrap_or(0);
        let avg = if count == 0 { 0.0 } else { total as f64 / count as f64 };
        out.push_str(&format!("- {}: {} active, hours={}, avg={:.1}\n", region, count, total, avg));
        grand_count += count;
        grand_hours += total;
        for (dept, hours) in depts {
            out.push_str(&format!("  * {} => {}\n", dept, hours));
        }
    }

    out.push_str(&format!("Grand total active: {}\nGrand total hours: {}\n", grand_count, grand_hours));
    out
}

fn main() {
    let entries = [
        Entry { region: "North", dept: "Sales", hours: 5, active: true },
        Entry { region: "North", dept: "Ops", hours: 8, active: true },
        Entry { region: "North", dept: "HR", hours: 0, active: true },
        Entry { region: "South", dept: "Sales", hours: 6, active: true },
        Entry { region: "South", dept: "Ops", hours: 3, active: true },
        Entry { region: "South", dept: "HR", hours: 0, active: false },
        Entry { region: "East", dept: "Sales", hours: 5, active: true },
        Entry { region: "East", dept: "Ops", hours: 7, active: true },
        Entry { region: "West", dept: "Sales", hours: 0, active: true },
        Entry { region: "West", dept: "Ops", hours: 0, active: false },
    ];

    print!("{}", build_report(&entries));
}
