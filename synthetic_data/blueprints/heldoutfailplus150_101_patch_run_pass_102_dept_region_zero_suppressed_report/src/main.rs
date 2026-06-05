use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy)]
struct Record {
    dept: &'static str,
    region: &'static str,
    employees: u32,
    open: u32,
    closed: u32,
    score: u32,
    active: bool,
}

#[derive(Default)]
struct DeptAgg {
    employees: u32,
    open: u32,
    closed: u32,
    score_sum: u32,
    count: u32,
    regions: BTreeSet<&'static str>,
}

fn main() {
    let rows = [
        Record { dept: "Engineering", region: "us", employees: 10, open: 6, closed: 4, score: 91, active: true },
        Record { dept: "Engineering", region: "eu", employees: 5, open: 3, closed: 2, score: 87, active: true },
        Record { dept: "Sales", region: "eu", employees: 7, open: 4, closed: 3, score: 90, active: true },
        Record { dept: "Sales", region: "apac", employees: 3, open: 0, closed: 3, score: 86, active: true },
        Record { dept: "Support", region: "us", employees: 4, open: 0, closed: 4, score: 79, active: true },
        Record { dept: "Support", region: "apac", employees: 3, open: 2, closed: 1, score: 81, active: true },
        Record { dept: "HR", region: "us", employees: 2, open: 0, closed: 2, score: 92, active: false },
        Record { dept: "Legal", region: "eu", employees: 1, open: 0, closed: 1, score: 77, active: true },
        Record { dept: "Ops", region: "us", employees: 2, open: 0, closed: 0, score: 70, active: true },
    ];

    let mut by_dept: BTreeMap<&str, DeptAgg> = BTreeMap::new();
    for r in rows {
        let agg = by_dept.entry(r.dept).or_default();
        agg.employees += r.employees;
        agg.open += r.open;
        agg.closed += r.closed;
        agg.score_sum += r.score;
        agg.count += 1;
        agg.regions.insert(r.region);
    }

    println!("ACTIVE DEPARTMENT REPORT");
    println!("Department | Regions | Employees | Open | Closed | Avg Score");

    let mut total_employees = 0;
    let mut total_open = 0;
    let mut total_closed = 0;
    let mut total_score_sum = 0;
    let mut total_count = 0;
    let mut total_regions: BTreeSet<&str> = BTreeSet::new();

    for (dept, agg) in by_dept {
        let avg = agg.score_sum as f64 / agg.count as f64;
        let regions = agg.regions.into_iter().collect::<Vec<_>>().join(", ");
        println!(
            "{} | {} | {} | {} | {} | {:.1}",
            dept, regions, agg.employees, agg.open, agg.closed, avg
        );
        total_employees += agg.employees;
        total_open += agg.open;
        total_closed += agg.closed;
        total_score_sum += agg.score_sum;
        total_count += agg.count;
        total_regions.extend(regions.split(", "));
    }

    let total_avg = total_score_sum as f64 / total_count as f64;
    println!(
        "TOTAL | {} | {} | {} | {} | {:.1}",
        total_regions.len(), total_employees, total_open, total_closed, total_avg
    );
}
