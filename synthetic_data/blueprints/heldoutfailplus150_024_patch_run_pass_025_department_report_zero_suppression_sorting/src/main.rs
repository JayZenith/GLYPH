struct Entry {
    dept: &'static str,
    active: bool,
    hours: u32,
    tickets: u32,
}

fn render_report(rows: &[Entry]) -> String {
    use std::collections::BTreeMap;

    let mut grouped: BTreeMap<&str, (u32, u32, u32)> = BTreeMap::new();
    for r in rows {
        let slot = grouped.entry(r.dept).or_insert((0, 0, 0));
        slot.0 += 1;
        slot.1 += r.hours;
        slot.2 += r.tickets;
    }

    let mut out = String::new();
    out.push_str("Department Report\n");
    out.push_str("Filter: active only\n");
    out.push_str("Dept | Employees | Hours | Tickets\n");

    let mut total_emp = 0;
    let mut total_hours = 0;
    let mut total_tickets = 0;

    for (dept, (emp, hours, tickets)) in grouped {
        total_emp += emp;
        total_hours += hours;
        total_tickets += tickets;
        out.push_str(&format!("{} | {} | {} | {}\n", dept, emp, hours, tickets));
    }

    out.push_str(&format!(
        "Summary | {} | {} | {}",
        total_emp, total_hours, total_tickets
    ));
    out
}

fn main() {
    let rows = vec![
        Entry { dept: "ENG", active: true, hours: 8, tickets: 3 },
        Entry { dept: "ENG", active: false, hours: 4, tickets: 1 },
        Entry { dept: "ENG", active: true, hours: 4, tickets: 1 },
        Entry { dept: "HR", active: true, hours: 0, tickets: 0 },
        Entry { dept: "OPS", active: true, hours: 7, tickets: 4 },
        Entry { dept: "OPS", active: true, hours: 2, tickets: 2 },
        Entry { dept: "SALES", active: false, hours: 6, tickets: 10 },
        Entry { dept: "SALES", active: true, hours: 5, tickets: 7 },
    ];

    println!("{}", render_report(&rows));
}
