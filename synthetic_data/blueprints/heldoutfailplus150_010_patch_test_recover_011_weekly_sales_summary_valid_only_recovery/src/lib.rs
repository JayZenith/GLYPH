use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone)]
pub struct SaleRecord {
    pub order_id: &'static str,
    pub region: &'static str,
    pub customer_id: &'static str,
    pub amount_cents: i64,
    pub week: u32,
    pub status: &'static str,
    pub refunded: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegionRow {
    pub region: String,
    pub orders: usize,
    pub unique_customers: usize,
    pub revenue_cents: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WeeklySummary {
    pub week: u32,
    pub total_orders: usize,
    pub total_unique_customers: usize,
    pub total_revenue_cents: i64,
    pub regions: Vec<RegionRow>,
}

pub fn summarize_week(records: &[SaleRecord], week: u32) -> WeeklySummary {
    let mut regions: HashMap<String, RegionRow> = HashMap::new();
    let mut customers: HashSet<String> = HashSet::new();

    for record in records {
        if record.week != week {
            continue;
        }
        if record.amount_cents <= 0 {
            continue;
        }

        let entry = regions.entry(record.region.to_string()).or_insert(RegionRow {
            region: record.region.to_string(),
            orders: 0,
            unique_customers: 0,
            revenue_cents: 0,
        });

        entry.orders += 1;
        entry.unique_customers += 1;
        entry.revenue_cents += record.amount_cents;
        customers.insert(record.customer_id.to_string());
    }

    let mut rows: Vec<RegionRow> = regions.into_values().collect();
    rows.sort_by(|a, b| a.region.cmp(&b.region));

    let total_orders = rows.iter().map(|r| r.orders).sum();
    let total_revenue_cents = rows.iter().map(|r| r.revenue_cents).sum();

    WeeklySummary {
        week,
        total_orders,
        total_unique_customers: customers.len(),
        total_revenue_cents,
        regions: rows,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_sales() -> Vec<SaleRecord> {
        vec![
            SaleRecord { order_id: "o1", region: "West", customer_id: "alice", amount_cents: 1200, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o2", region: "West", customer_id: "alice", amount_cents: 800, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o3", region: "East", customer_id: "bob", amount_cents: 2500, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o4", region: "East", customer_id: "carol", amount_cents: 2500, week: 18, status: "pending", refunded: false },
            SaleRecord { order_id: "o5", region: "North", customer_id: "dave", amount_cents: 1500, week: 18, status: "completed", refunded: true },
            SaleRecord { order_id: "o6", region: "South", customer_id: "erin", amount_cents: 2500, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o7", region: "South", customer_id: "erin", amount_cents: 0, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o8", region: "Central", customer_id: "frank", amount_cents: 2500, week: 18, status: "completed", refunded: false },
            SaleRecord { order_id: "o9", region: "West", customer_id: "gina", amount_cents: 500, week: 19, status: "completed", refunded: false },
            SaleRecord { order_id: "o10", region: "West", customer_id: "henry", amount_cents: -200, week: 18, status: "completed", refunded: false },
        ]
    }

    #[test]
    fn filters_to_valid_completed_non_refunded_sales_for_the_week() {
        let summary = summarize_week(&sample_sales(), 18);
        assert_eq!(summary.total_orders, 5);
        assert_eq!(summary.total_revenue_cents, 9500);
        assert_eq!(summary.total_unique_customers, 4);
    }

    #[test]
    fn counts_unique_customers_per_region_not_orders() {
        let summary = summarize_week(&sample_sales(), 18);
        let west = summary.regions.iter().find(|r| r.region == "West").unwrap();
        assert_eq!(west.orders, 2);
        assert_eq!(west.unique_customers, 1);
        assert_eq!(west.revenue_cents, 2000);
    }

    #[test]
    fn sorts_regions_by_revenue_desc_then_orders_desc_then_name() {
        let summary = summarize_week(&sample_sales(), 18);
        let names: Vec<_> = summary.regions.iter().map(|r| r.region.as_str()).collect();
        assert_eq!(names, vec!["East", "Central", "South", "West"]);
    }

    #[test]
    fn excludes_regions_with_no_valid_sales() {
        let summary = summarize_week(&sample_sales(), 18);
        assert!(summary.regions.iter().all(|r| r.region != "North"));
        assert!(summary.regions.iter().all(|r| r.region != "East" || r.orders == 1));
    }
}
