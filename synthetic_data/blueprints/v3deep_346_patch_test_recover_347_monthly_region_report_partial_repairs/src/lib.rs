use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct Order {
    pub month: &'static str,
    pub region: &'static str,
    pub shipped: bool,
    pub amount_cents: i32,
}

pub fn monthly_region_report(orders: &[Order]) -> String {
    let mut groups: BTreeMap<&str, (usize, i32)> = BTreeMap::new();

    for order in orders {
        if order.amount_cents < 0 {
            continue;
        }

        let entry = groups.entry(order.region).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += order.amount_cents;
    }

    let mut lines = Vec::new();
    for (region, (count, total)) in groups {
        let dollars = total as f64 / 100.0;
        lines.push(format!("{}: {} orders ${:.2}", region, count, dollars));
    }

    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_orders() -> Vec<Order> {
        vec![
            Order { month: "2024-05", region: "West", shipped: true, amount_cents: 1200 },
            Order { month: "2024-05", region: "West", shipped: false, amount_cents: 900 },
            Order { month: "2024-05", region: "East", shipped: true, amount_cents: 500 },
            Order { month: "2024-05", region: "East", shipped: true, amount_cents: -50 },
            Order { month: "2024-05", region: "North", shipped: true, amount_cents: 250 },
            Order { month: "2024-06", region: "West", shipped: true, amount_cents: 700 },
            Order { month: "2024-05", region: "", shipped: true, amount_cents: 400 },
        ]
    }

    #[test]
    fn aggregates_only_requested_month_and_shipped_orders() {
        let report = monthly_region_report(&sample_orders());
        assert!(report.contains("West: 1 shipped $12.00"));
        assert!(report.contains("East: 1 shipped $5.00"));
        assert!(report.contains("North: 1 shipped $2.50"));
        assert!(!report.contains("$9.00"));
        assert!(!report.contains("$7.00"));
    }

    #[test]
    fn omits_blank_regions_and_sorts_by_total_desc_then_name() {
        let report = monthly_region_report(&sample_orders());
        let lines: Vec<_> = report.lines().collect();
        assert_eq!(
            lines,
            vec![
                "West: 1 shipped $12.00",
                "East: 1 shipped $5.00",
                "North: 1 shipped $2.50",
            ]
        );
    }

    #[test]
    fn empty_report_when_no_valid_shipped_orders() {
        let orders = vec![
            Order { month: "2024-05", region: "West", shipped: false, amount_cents: 100 },
            Order { month: "2024-06", region: "West", shipped: true, amount_cents: 100 },
            Order { month: "2024-05", region: "", shipped: true, amount_cents: 100 },
            Order { month: "2024-05", region: "East", shipped: true, amount_cents: -1 },
        ];
        assert_eq!(monthly_region_report(&orders), "");
    }
}
