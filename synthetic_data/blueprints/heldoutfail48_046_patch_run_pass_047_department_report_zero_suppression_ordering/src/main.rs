struct Entry {
    dept: &'static str,
    status: &'static str,
    amount: i32,
}

fn main() {
    let rows = [
        Entry { dept: "East", status: "active", amount: 40 },
        Entry { dept: "East", status: "active", amount: 20 },
        Entry { dept: "East", status: "cancelled", amount: 5 },
        Entry { dept: "North", status: "active", amount: 0 },
        Entry { dept: "North", status: "inactive", amount: 0 },
        Entry { dept: "South", status: "active", amount: 25 },
        Entry { dept: "South", status: "inactive", amount: 0 },
        Entry { dept: "South", status: "cancelled", amount: 11 },
        Entry { dept: "West", status: "inactive", amount: 0 },
        Entry { dept: "West", status: "active", amount: 20 },
        Entry { dept: "West", status: "cancelled", amount: -3 },
        Entry { dept: "Central", status: "active", amount: -5 },
        Entry { dept: "Central", status: "inactive", amount: 5 },
    ];

    let mut depts: Vec<&str> = Vec::new();
    for r in &rows {
        if !depts.contains(&r.dept) {
            depts.push(r.dept);
        }
    }
    depts.sort();

    println!("Department Report");

    let mut shown = 0;
    let mut grand_tx = 0;
    let mut grand_active = 0;
    let mut grand_amount = 0;

    for dept in depts {
        let mut tx = 0;
        let mut active = 0;
        let mut amount = 0;

        for r in &rows {
            if r.dept == dept {
                tx += 1;
                amount += r.amount;
                if r.status == "active" {
                    active += 1;
                }
            }
        }

        if tx == 0 {
            continue;
        }

        println!("- {}: transactions={} active={} amount={}", dept, tx, active, amount);
        shown += 1;
        grand_tx += tx;
        grand_active += active;
        grand_amount += amount;
    }

    println!(
        "Summary: departments={} transactions={} active={} amount={}",
        shown, grand_tx, grand_active, grand_amount
    );
}
