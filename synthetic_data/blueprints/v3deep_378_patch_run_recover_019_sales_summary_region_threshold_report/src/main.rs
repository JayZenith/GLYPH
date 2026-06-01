use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Order {
    region: &'static str,
    amount: i32,
    refunded: bool,
}

fn main() {
    let orders = [
        Order { region: "North", amount: 700, refunded: false },
        Order { region: "North", amount: 300, refunded: false },
        Order { region: "North", amount: 50, refunded: true },
        Order { region: "South", amount: 450, refunded: false },
        Order { region: "South", amount: 550, refunded: false },
        Order { region: "East", amount: 400, refunded: false },
        Order { region: "East", amount: 200, refunded: false },
        Order { region: "West", amount: 200, refunded: false },
        Order { region: "West", amount: 800, refunded: false },
    ];

    let mut totals: BTreeMap<&str, (i32, i32)> = BTreeMap::new();
    for order in orders {
        let entry = totals.entry(order.region).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += order.amount;
    }

    let mut lines = vec!["Sales Summary".to_string()];
    let mut grand_total = 0;

    for (region, (count, revenue)) in totals {
        if revenue >= 1000 {
            grand_total += count;
            let avg = count / revenue;
            lines.push(format!("{} | orders={} | revenue={} | avg={}", region, revenue, count, avg));
        }
    }

    lines.push(format!("Grand total revenue: {}", grand_total));
    println!("{}", lines.join("\n"));
}
