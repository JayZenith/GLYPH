use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Row {
    region: &'static str,
    dept: &'static str,
    employees: i32,
    contractors: i32,
    active: bool,
    hours: i32,
}

fn rows() -> Vec<Row> {
    vec![
        Row { region: "North", dept: "Sales", employees: 2, contractors: 0, active: true, hours: 8 },
        Row { region: "North", dept: "Sales", employees: 1, contractors: 0, active: false, hours: 7 },
        Row { region: "North", dept: "Support", employees: 1, contractors: 0, active: true, hours: 4 },
        Row { region: "South", dept: "Sales", employees: 3, contractors: 0, active: true, hours: 0 },
        Row { region: "South", dept: "Support", employees: 0, contractors: 2, active: true, hours: 9 },
        Row { region: "East", dept: "Ops", employees: 0, contractors: 0, active: true, hours: 3 },
        Row { region: "West", dept: "Support", employees: 1, contractors: 1, active: true, hours: 6 },
        Row { region: "West", dept: "Support", employees: 1, contractors: 0, active: false, hours: 2 },
        Row { region: "West", dept: "Sales", employees: 1, contractors: 0, active: true, hours: 5 },
    ]
}

fn build_report(rows: &[Row]) -> String {
    let mut groups: BTreeMap<(&str, &str), (i32, i32, i32)> = BTreeMap::new();
    let mut region_totals: BTreeMap<&str, (i32, i32)> = BTreeMap::new();

    for r in rows {
        if !r.active || r.hours < 0 {
            continue;
        }
        let headcount = r.employees;
        let entry = groups.entry((r.region, r.dept)).or_insert((0, 0, 0));
        entry.0 += headcount;
        entry.1 += 1;
        entry.2 += r.hours;

        let reg = region_totals.entry(r.region).or_insert((0, 0));
        reg.0 += 1;
        reg.1 += r.hours;
    }

    let mut out = String::from("Department Report\n");
    for ((region, dept), (headcount, active, hours)) in groups {
        out.push_str(&format!("{} / {}: headcount={}, active={}, hours={}\n", region, dept, headcount, active, hours));
    }
    out.push_str("-- Region Totals --\n");
    for (region, (active, hours)) in region_totals {
        out.push_str(&format!("{}: active={}, hours={}\n", region, active, hours));
    }
    out.push_str(&format!("Grand Total: active={}, hours={}",
        rows.iter().filter(|r| r.active).count(),
        rows.iter().filter(|r| r.active).map(|r| r.hours).sum::<i32>()
    ));
    out
}

fn main() {
    println!("{}", build_report(&rows()));
}
