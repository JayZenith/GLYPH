use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    dept: &'static str,
    region: &'static str,
    active: bool,
    units: i32,
    revenue: i32,
}

fn rows() -> Vec<Row> {
    vec![
        Row { dept: "Sales", region: "East", active: true, units: 10, revenue: 2500 },
        Row { dept: "Sales", region: "West", active: true, units: 0, revenue: 100 },
        Row { dept: "Sales", region: "North", active: false, units: 7, revenue: 700 },
        Row { dept: "Support", region: "North", active: true, units: 5, revenue: 0 },
        Row { dept: "Support", region: "West", active: true, units: 1, revenue: 0 },
        Row { dept: "Research", region: "East", active: true, units: 0, revenue: 0 },
        Row { dept: "Research", region: "South", active: true, units: 0, revenue: 50 },
        Row { dept: "HR", region: "South", active: false, units: 3, revenue: 0 },
    ]
}

fn build_report(rows: &[Row]) -> String {
    let mut dept_map: BTreeMap<&str, BTreeMap<&str, (i32, i32)>> = BTreeMap::new();

    for row in rows {
        let region_map = dept_map.entry(row.dept).or_default();
        let entry = region_map.entry(row.region).or_insert((0, 0));
        entry.0 += row.units;
        entry.1 += row.revenue;
    }

    let mut out = String::from("Department Report\n");
    let mut grand_units = 0;
    let mut grand_revenue = 0;

    for (dept, regions) in dept_map {
        let mut dept_units = 0;
        let mut dept_revenue = 0;
        for (_region, (units, revenue)) in &regions {
            dept_units += *units;
            dept_revenue += *revenue;
        }

        out.push_str(&format!("{} | units={} | revenue={}\n", dept, dept_units, dept_revenue));
        grand_units += dept_units;
        grand_revenue += dept_revenue;

        for (region, (units, revenue)) in regions {
            out.push_str(&format!("  {}: units={} revenue={}\n", region, units, revenue));
        }
    }

    out.push_str(&format!("Totals | units={} | revenue={}", grand_units, grand_revenue));
    out
}

fn main() {
    println!("{}", build_report(&rows()));
}
