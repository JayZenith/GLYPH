use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    dept: &'static str,
    region: &'static str,
    units: i32,
    revenue_cents: i32,
    active: bool,
}

fn rows() -> Vec<Row> {
    vec![
        Row { dept: "Sales", region: "East", units: 4, revenue_cents: 10000, active: true },
        Row { dept: "Sales", region: "West", units: 0, revenue_cents: 2500, active: true },
        Row { dept: "Sales", region: "East", units: 3, revenue_cents: 5500, active: true },
        Row { dept: "Support", region: "East", units: 0, revenue_cents: 0, active: true },
        Row { dept: "Support", region: "West", units: 2, revenue_cents: 7000, active: false },
        Row { dept: "Ops", region: "North", units: 9, revenue_cents: 15000, active: true },
        Row { dept: "Ops", region: "East", units: 1, revenue_cents: 500, active: true },
        Row { dept: "Legal", region: "HQ", units: 0, revenue_cents: 2000, active: true },
        Row { dept: "East", region: "Remote", units: 8, revenue_cents: 8000, active: true },
        Row { dept: "East", region: "West", units: 2, revenue_cents: 2000, active: true },
    ]
}

fn render_report(rows: &[Row]) -> String {
    let mut groups: BTreeMap<&str, (usize, i32, i32)> = BTreeMap::new();

    for row in rows {
        if row.region == "West" {
            continue;
        }
        let entry = groups.entry(row.region).or_insert((0, 0, 0));
        entry.0 += 1;
        entry.1 += row.units;
        entry.2 += row.revenue_cents;
    }

    let mut out = String::from("Department Report\n");
    let mut total_count = 0usize;
    let mut total_units = 0i32;
    let mut total_revenue = 0i32;

    for (name, (count, units, revenue)) in groups {
        total_count += count;
        total_units += units;
        total_revenue += revenue;
        out.push_str(&format!("- {}: count={}, units={}, revenue={:.1}\n", name, count, units, revenue as f64 / 100.0));
    }

    out.push_str(&format!(
        "Grand Total: count={}, units={}, revenue={:.1}",
        total_count,
        total_units,
        total_revenue as f64 / 100.0
    ));
    out
}

fn main() {
    println!("{}", render_report(&rows()));
}
