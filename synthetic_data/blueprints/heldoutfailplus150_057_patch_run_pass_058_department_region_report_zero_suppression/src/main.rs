use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Entry {
    region: &'static str,
    dept: &'static str,
    employee: &'static str,
    hours: f32,
    active: bool,
}

fn sample() -> Vec<Entry> {
    vec![
        Entry { region: "North", dept: "Engineering", employee: "Ann", hours: 5.5, active: true },
        Entry { region: "North", dept: "Engineering", employee: "Ben", hours: 2.5, active: true },
        Entry { region: "North", dept: "Support", employee: "Cara", hours: 4.0, active: true },
        Entry { region: "North", dept: "Sales", employee: "Drew", hours: 0.0, active: true },
        Entry { region: "South", dept: "Support", employee: "Eli", hours: 3.0, active: true },
        Entry { region: "South", dept: "Support", employee: "Fay", hours: 4.0, active: true },
        Entry { region: "South", dept: "Engineering", employee: "Gus", hours: 0.0, active: true },
        Entry { region: "South", dept: "Sales", employee: "Hal", hours: 1.0, active: false },
        Entry { region: "West", dept: "Support", employee: "Ian", hours: 0.0, active: true },
        Entry { region: "West", dept: "Engineering", employee: "Jae", hours: 0.0, active: false },
    ]
}

fn build_report(entries: &[Entry]) -> String {
    let mut grouped: BTreeMap<&str, BTreeMap<&str, (usize, f32)>> = BTreeMap::new();

    for e in entries {
        let dept_map = grouped.entry(e.region).or_default();
        let stat = dept_map.entry(e.dept).or_insert((0, 0.0));
        stat.0 += 1;
        stat.1 += e.hours;
    }

    let mut out = String::new();
    out.push_str("ACTIVE EMPLOYEE HOURS REPORT\n");

    let mut grand_count = 0usize;
    let mut grand_hours = 0.0f32;

    for (region, depts) in grouped {
        out.push_str(&format!("Region {}\n", region));
        let mut region_count = 0usize;
        let mut region_hours = 0.0f32;

        for (dept, (count, hours)) in depts {
            out.push_str(&format!("  {}: {} employees, {:.1} hrs\n", dept, count, hours));
            region_count += count;
            region_hours += hours;
        }

        out.push_str(&format!("  TOTAL: {} employees, {:.1} hrs\n", region_count, region_hours));
        grand_count += region_count;
        grand_hours += region_hours;
    }

    out.push_str(&format!("GRAND TOTAL: {} employees, {:.1} hrs\n", grand_count, grand_hours));
    out
}

fn main() {
    print!("{}", build_report(&sample()));
}
