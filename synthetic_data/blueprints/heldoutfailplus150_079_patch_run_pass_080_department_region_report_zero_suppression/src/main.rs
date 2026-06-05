use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    region: &'static str,
    dept: &'static str,
    amount: f64,
    active: bool,
}

fn rows() -> Vec<Row> {
    vec![
        Row { region: "North", dept: "Sales", amount: 80.0, active: true },
        Row { region: "North", dept: "Sales", amount: -25.0, active: true },
        Row { region: "North", dept: "Ops", amount: 100.0, active: true },
        Row { region: "North", dept: "Support", amount: 0.0, active: true },
        Row { region: "North", dept: "Ops", amount: 40.0, active: false },
        Row { region: "East", dept: "Ops", amount: 120.0, active: true },
        Row { region: "East", dept: "Sales", amount: 60.0, active: true },
        Row { region: "East", dept: "Support", amount: -10.0, active: true },
        Row { region: "West", dept: "Support", amount: 90.0, active: true },
        Row { region: "West", dept: "Sales", amount: 0.0, active: true },
        Row { region: "South", dept: "Ops", amount: 0.0, active: true },
        Row { region: "South", dept: "Sales", amount: -5.0, active: true },
    ]
}

fn build_report(rows: &[Row]) -> String {
    let mut by_region: BTreeMap<&str, BTreeMap<&str, f64>> = BTreeMap::new();

    for row in rows {
        let dept_map = by_region.entry(row.region).or_default();
        *dept_map.entry(row.dept).or_insert(0.0) += row.amount;
    }

    let mut out = String::from("REGION REPORT\n");

    for (region, dept_map) in by_region {
        let region_total: f64 = dept_map.values().copied().sum();
        out.push_str(&format!("{} | total={:.0} | departments={}\n", region, region_total, dept_map.len()));
        for (dept, total) in dept_map {
            out.push_str(&format!("  {}: {:.0}\n", dept, total));
        }
    }

    out.trim_end().to_string()
}

fn main() {
    println!("{}", build_report(&rows()));
}
