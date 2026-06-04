use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    region: &'static str,
    dept: &'static str,
    items: i32,
    revenue: i32,
    active: bool,
}

fn rows() -> Vec<Row> {
    vec![
        Row { region: "North", dept: "Sales", items: 3, revenue: 90, active: true },
        Row { region: "North", dept: "Sales", items: 2, revenue: 35, active: true },
        Row { region: "North", dept: "Ops", items: 7, revenue: 200, active: true },
        Row { region: "North", dept: "Support", items: 0, revenue: 40, active: true },
        Row { region: "South", dept: "Sales", items: 8, revenue: 210, active: true },
        Row { region: "South", dept: "Ops", items: 0, revenue: 75, active: true },
        Row { region: "South", dept: "Support", items: 2, revenue: 50, active: false },
        Row { region: "East", dept: "Sales", items: 1, revenue: 25, active: false },
        Row { region: "East", dept: "Ops", items: 0, revenue: 0, active: true },
        Row { region: "West", dept: "Support", items: 5, revenue: 120, active: true },
        Row { region: "West", dept: "Ops", items: 4, revenue: 110, active: true },
        Row { region: "West", dept: "Sales", items: 0, revenue: 10, active: true },
    ]
}

fn build_report() -> String {
    let mut grouped: BTreeMap<&str, BTreeMap<&str, (i32, i32)>> = BTreeMap::new();

    for row in rows() {
        let dept_map = grouped.entry(row.region).or_default();
        let totals = dept_map.entry(row.dept).or_insert((0, 0));
        totals.0 += row.items;
        totals.1 += row.revenue;
    }

    let mut out = String::new();
    for (region, dept_map) in grouped {
        out.push_str(&format!("{}\n", region));
        let mut region_items = 0;
        let mut region_revenue = 0;
        for (dept, (items, revenue)) in dept_map {
            region_items += items;
            region_revenue += revenue;
            out.push_str(&format!("  {}: {} items, ${}\n", dept, items, revenue));
        }
        out.push_str(&format!("  TOTAL: {} items, ${}\n\n", region_items, region_revenue));
    }

    out.trim_end().to_string()
}

fn main() {
    println!("{}", build_report());
}
