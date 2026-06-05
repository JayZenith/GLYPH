use std::collections::{BTreeMap, BTreeSet, HashMap};

#[derive(Clone, Debug)]
pub struct Order {
    pub week: u32,
    pub customer_id: &'static str,
    pub category: &'static str,
    pub amount_cents: i64,
    pub refunded: bool,
    pub canceled: bool,
}

pub fn weekly_report(orders: &[Order]) -> Vec<String> {
    let mut weeks: HashMap<u32, Vec<&Order>> = HashMap::new();
    for order in orders {
        weeks.entry(order.week).or_default().push(order);
    }

    let mut out = Vec::new();
    let mut week_ids: Vec<u32> = weeks.keys().copied().collect();
    week_ids.sort();

    for week in week_ids {
        let bucket = &weeks[&week];
        let valid_orders: Vec<&Order> = bucket.iter().copied().filter(|o| !o.canceled).collect();
        let gross_cents: i64 = valid_orders.iter().map(|o| o.amount_cents).sum();
        let unique_customers = valid_orders.len();

        let mut category_totals: HashMap<&str, i64> = HashMap::new();
        for order in &valid_orders {
            *category_totals.entry(order.category).or_insert(0) += order.amount_cents;
        }

        let mut categories: Vec<(&str, i64)> = category_totals.into_iter().collect();
        categories.sort_by(|a, b| a.0.cmp(b.0));

        let cats = categories
            .into_iter()
            .map(|(name, total)| format!("{}={}", name, total))
            .collect::<Vec<_>>()
            .join(",");

        out.push(format!(
            "week={} valid_orders={} unique_customers={} gross_cents={} categories=[{}]",
            week,
            valid_orders.len(),
            unique_customers,
            gross_cents,
            cats
        ));
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_orders() -> Vec<Order> {
        vec![
            Order { week: 202401, customer_id: "alice", category: "books", amount_cents: 1200, refunded: false, canceled: false },
            Order { week: 202401, customer_id: "alice", category: "games", amount_cents: 3000, refunded: false, canceled: false },
            Order { week: 202401, customer_id: "bob", category: "books", amount_cents: 1200, refunded: true, canceled: false },
            Order { week: 202401, customer_id: "cara", category: "garden", amount_cents: 3000, refunded: false, canceled: true },
            Order { week: 202402, customer_id: "dan", category: "tools", amount_cents: 5000, refunded: false, canceled: false },
            Order { week: 202402, customer_id: "erin", category: "books", amount_cents: 5000, refunded: false, canceled: false },
            Order { week: 202402, customer_id: "dan", category: "books", amount_cents: 2000, refunded: false, canceled: false },
            Order { week: 202402, customer_id: "fran", category: "games", amount_cents: 7000, refunded: true, canceled: false },
        ]
    }

    #[test]
    fn excludes_refunded_and_canceled_from_all_aggregates() {
        let report = weekly_report(&sample_orders());
        assert_eq!(
            report,
            vec![
                "week=202402 valid_orders=3 unique_customers=2 gross_cents=12000 categories=[books=7000,tools=5000]",
                "week=202401 valid_orders=2 unique_customers=1 gross_cents=4200 categories=[games=3000,books=1200]",
            ]
        );
    }

    #[test]
    fn counts_unique_customers_per_week_not_rows() {
        let orders = vec![
            Order { week: 9, customer_id: "u1", category: "a", amount_cents: 100, refunded: false, canceled: false },
            Order { week: 9, customer_id: "u1", category: "b", amount_cents: 200, refunded: false, canceled: false },
            Order { week: 9, customer_id: "u2", category: "a", amount_cents: 300, refunded: false, canceled: false },
        ];
        let report = weekly_report(&orders);
        assert_eq!(
            report,
            vec!["week=9 valid_orders=3 unique_customers=2 gross_cents=600 categories=[a=400,b=200]"]
        );
    }

    #[test]
    fn sorts_weeks_descending_and_categories_by_total_then_name() {
        let orders = vec![
            Order { week: 1, customer_id: "x", category: "beta", amount_cents: 400, refunded: false, canceled: false },
            Order { week: 1, customer_id: "y", category: "alpha", amount_cents: 400, refunded: false, canceled: false },
            Order { week: 2, customer_id: "z", category: "delta", amount_cents: 100, refunded: false, canceled: false },
        ];
        let report = weekly_report(&orders);
        assert_eq!(
            report,
            vec![
                "week=2 valid_orders=1 unique_customers=1 gross_cents=100 categories=[delta=100]",
                "week=1 valid_orders=2 unique_customers=2 gross_cents=800 categories=[alpha=400,beta=400]",
            ]
        );
    }

    #[test]
    fn skips_weeks_with_no_valid_orders_entirely() {
        let orders = vec![
            Order { week: 7, customer_id: "a", category: "books", amount_cents: 1000, refunded: true, canceled: false },
            Order { week: 7, customer_id: "b", category: "games", amount_cents: 2000, refunded: false, canceled: true },
            Order { week: 8, customer_id: "c", category: "books", amount_cents: 1500, refunded: false, canceled: false },
        ];
        let report = weekly_report(&orders);
        assert_eq!(
            report,
            vec!["week=8 valid_orders=1 unique_customers=1 gross_cents=1500 categories=[books=1500]"]
        );
    }
}
