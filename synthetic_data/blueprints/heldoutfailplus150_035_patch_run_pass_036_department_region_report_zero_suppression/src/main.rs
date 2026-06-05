struct Record {
    dept: &'static str,
    region: &'static str,
    projects: i32,
    spend: i32,
    active: bool,
}

fn build_report(records: &[Record]) -> String {
    let mut rows: Vec<(String, String, i32, i32)> = Vec::new();

    for r in records {
        if !r.active {
            continue;
        }
        rows.push((
            r.region.to_string(),
            r.dept.to_string(),
            r.projects,
            r.spend,
        ));
    }

    rows.sort();

    let mut out = String::from("DEPARTMENT REPORT\n");
    let mut current_region = String::new();
    let mut region_projects = 0;
    let mut region_spend = 0;

    for (region, dept, projects, spend) in rows {
        if current_region != region {
            if !current_region.is_empty() {
                out.push_str(&format!("  Total: projects={}, spend=${}\n", region_projects, region_spend));
            }
            current_region = region.clone();
            region_projects = 0;
            region_spend = 0;
            out.push_str(&format!("- {}\n", current_region));
        }

        region_projects += projects;
        region_spend += spend;
        out.push_str(&format!("  {}: projects={}, spend=${}\n", dept, projects, spend));
    }

    if !current_region.is_empty() {
        out.push_str(&format!("  Total: projects={}, spend=${}", region_projects, region_spend));
    }

    out
}

fn main() {
    let records = vec![
        Record { dept: "Sales", region: "East", projects: 2, spend: 500, active: true },
        Record { dept: "Sales", region: "East", projects: 1, spend: 500, active: true },
        Record { dept: "Support", region: "East", projects: 0, spend: 300, active: true },
        Record { dept: "Engineering", region: "East", projects: 5, spend: 1200, active: true },
        Record { dept: "Engineering", region: "East", projects: 1, spend: 800, active: true },
        Record { dept: "Support", region: "West", projects: 4, spend: 400, active: true },
        Record { dept: "Support", region: "West", projects: 2, spend: 300, active: true },
        Record { dept: "Sales", region: "West", projects: 3, spend: 700, active: true },
        Record { dept: "Engineering", region: "West", projects: 0, spend: 1000, active: true },
        Record { dept: "Sales", region: "North", projects: 0, spend: 0, active: true },
        Record { dept: "HR", region: "East", projects: 2, spend: 200, active: false },
    ];

    print!("{}", build_report(&records));
}
