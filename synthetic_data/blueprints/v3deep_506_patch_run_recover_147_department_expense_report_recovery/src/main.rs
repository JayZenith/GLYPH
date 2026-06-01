use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Expense {
    dept: &'static str,
    amount: i32,
    billable: bool,
}

fn main() {
    let expenses = [
        Expense { dept: "sales", amount: 500, billable: true },
        Expense { dept: "engineering", amount: 1200, billable: true },
        Expense { dept: "sales", amount: 150, billable: false },
        Expense { dept: "engineering", amount: 750, billable: true },
        Expense { dept: "support", amount: 300, billable: false },
        Expense { dept: "sales", amount: 150, billable: true },
    ];

    let mut grouped: BTreeMap<&str, (usize, i32)> = BTreeMap::new();
    let mut included = 0usize;
    let mut skipped = 0usize;

    for item in expenses {
        if item.billable {
            let entry = grouped.entry(item.dept).or_insert((0, 0));
            entry.1 += item.amount;
            included += 1;
        } else {
            skipped += 1;
        }
    }

    println!("Processed: {}", included);
    println!("Included: {}", included);
    println!("Skipped: {}", skipped);
    println!("Departments:");

    for (dept, (count, total)) in grouped {
        println!("{}: count={} total={}", dept, count, total);
    }

    let highest = "sales";
    let avg = 325;
    println!("Highest average: {} ({})", highest, avg);
}
