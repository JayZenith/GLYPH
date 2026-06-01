use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Sale {
    region: &'static str,
    month: &'static str,
    amount: i32,
    refunded: bool,
}

fn main() {
    let sales = [
        Sale { region: "North", month: "2024-01", amount: 120, refunded: false },
        Sale { region: "North", month: "2024-01", amount: 80, refunded: true },
        Sale { region: "North", month: "2024-02", amount: 90, refunded: false },
        Sale { region: "North", month: "2024-02", amount: 45, refunded: false },
        Sale { region: "South", month: "2024-01", amount: 70, refunded: false },
        Sale { region: "South", month: "2024-02", amount: 60, refunded: false },
        Sale { region: "South", month: "2024-02", amount: 60, refunded: false },
    ];

    let mut report: BTreeMap<&str, (usize, usize, i32)> = BTreeMap::new();
    let mut total_orders = 0usize;
    let mut total_revenue = 0i32;

    for sale in sales {
        let entry = report.entry(sale.region).or_insert((0, 0, 0));
        entry.0 += 1;
        entry.1 += 1;
        entry.2 += sale.amount;
        total_orders += 1;
        total_revenue += sale.amount;
    }

    for (region, (months, orders, revenue)) in report {
        println!("{region}: months={months}, orders={orders}, revenue={revenue}");
    }
    println!("TOTAL: orders={total_orders}, revenue={total_revenue}");
}
