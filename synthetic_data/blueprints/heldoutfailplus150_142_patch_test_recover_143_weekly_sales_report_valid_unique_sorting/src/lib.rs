use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub struct SaleRecord {
    pub week: &'static str,
    pub region: &'static str,
    pub order_id: &'static str,
    pub customer_id: &'static str,
    pub amount_cents: i64,
    pub status: &'static str,
}

pub fn weekly_region_report(records: &[SaleRecord]) -> String {
    let mut totals: BTreeMap<&str, (i64, usize, BTreeSet<&str>)> = BTreeMap::new();

    for r in records {
        if r.status != "valid" && r.amount_cents < 0 {
            continue;
        }
        let entry = totals.entry(r.region).or_insert((0, 0, BTreeSet::new()));
        entry.0 += r.amount_cents;
        entry.1 += 1;
        entry.2.insert(r.customer_id);
    }

    let mut rows: Vec<_> = totals
        .into_iter()
        .map(|(region, (amount, orders, customers))| (region, amount, orders, customers.len()))
        .collect();

    rows.sort_by(|a, b| a.0.cmp(b.0));

    let mut out = String::from("region,total_cents,orders,unique_customers\n");
    for (region, amount, orders, customers) in rows {
        out.push_str(&format!("{region},{amount},{orders},{customers}\n"));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_data() -> Vec<SaleRecord> {
        vec![
            SaleRecord { week: "2024-W18", region: "North", order_id: "N-100", customer_id: "C1", amount_cents: 1200, status: "valid" },
            SaleRecord { week: "2024-W18", region: "North", order_id: "N-100", customer_id: "C1", amount_cents: 1200, status: "valid" },
            SaleRecord { week: "2024-W18", region: "North", order_id: "N-101", customer_id: "C2", amount_cents: 800, status: "returned" },
            SaleRecord { week: "2024-W18", region: "South", order_id: "S-200", customer_id: "C3", amount_cents: 2500, status: "valid" },
            SaleRecord { week: "2024-W18", region: "South", order_id: "S-201", customer_id: "C3", amount_cents: 500, status: "valid" },
            SaleRecord { week: "2024-W18", region: "South", order_id: "S-202", customer_id: "C4", amount_cents: -300, status: "valid" },
            SaleRecord { week: "2024-W18", region: "West", order_id: "W-300", customer_id: "C5", amount_cents: 2200, status: "valid" },
            SaleRecord { week: "2024-W17", region: "West", order_id: "W-301", customer_id: "C6", amount_cents: 9999, status: "valid" },
            SaleRecord { week: "2024-W18", region: "East", order_id: "E-400", customer_id: "C7", amount_cents: 2500, status: "valid" },
            SaleRecord { week: "2024-W18", region: "East", order_id: "E-401", customer_id: "C8", amount_cents: 500, status: "cancelled" },
            SaleRecord { week: "2024-W18", region: "Central", order_id: "C-500", customer_id: "C9", amount_cents: 0, status: "valid" },
            SaleRecord { week: "2024-W18", region: "Central", order_id: "C-501", customer_id: "C9", amount_cents: 700, status: "valid" },
        ]
    }

    #[test]
    fn report_includes_only_target_week_and_valid_positive_rows() {
        let report = weekly_region_report(&sample_data());
        assert!(!report.contains("9999"), "must exclude other weeks");
        assert!(!report.contains("returned"), "must exclude non-valid rows");
        assert!(!report.contains(",-300,"), "must exclude non-positive amounts");
        assert_eq!(
            report,
            concat!(
                "region,total_cents,orders,unique_customers\n",
                "East,2500,1,1\n",
                "South,3000,2,1\n",
                "West,2200,1,1\n",
                "North,1200,1,1\n",
                "Central,700,1,1\n"
            )
        );
    }

    #[test]
    fn report_deduplicates_orders_before_counting_and_summing() {
        let report = weekly_region_report(&sample_data());
        assert!(report.contains("North,1200,1,1\n"), "duplicate order_id should count once");
        assert!(!report.contains("North,2400,2,1\n"), "duplicate order_id should not double count");
    }

    #[test]
    fn report_sorts_by_total_desc_then_region_asc() {
        let report = weekly_region_report(&sample_data());
        let lines: Vec<&str> = report.lines().skip(1).collect();
        assert_eq!(
            lines,
            vec![
                "East,2500,1,1",
                "South,3000,2,1",
                "West,2200,1,1",
                "North,1200,1,1",
                "Central,700,1,1",
            ]
        );
    }

    #[test]
    fn report_tiebreaks_equal_totals_by_region_name() {
        let data = vec![
            SaleRecord { week: "2024-W18", region: "Gamma", order_id: "G-1", customer_id: "A", amount_cents: 1500, status: "valid" },
            SaleRecord { week: "2024-W18", region: "Alpha", order_id: "A-1", customer_id: "B", amount_cents: 1500, status: "valid" },
            SaleRecord { week: "2024-W18", region: "Beta", order_id: "B-1", customer_id: "C", amount_cents: 1000, status: "valid" },
        ];
        let report = weekly_region_report(&data);
        let lines: Vec<&str> = report.lines().skip(1).collect();
        assert_eq!(lines, vec!["Alpha,1500,1,1", "Gamma,1500,1,1", "Beta,1000,1,1"]);
    }
}
