use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone)]
pub struct SaleRecord {
    pub week: u32,
    pub rep: String,
    pub customer_id: String,
    pub amount_cents: i64,
    pub valid: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RepSummary {
    pub rep: String,
    pub orders: usize,
    pub unique_customers: usize,
    pub revenue_cents: i64,
}

pub fn weekly_summary(records: &[SaleRecord], week: u32) -> Vec<RepSummary> {
    let mut by_rep: HashMap<String, Vec<&SaleRecord>> = HashMap::new();

    for record in records {
        if record.week == week {
            by_rep.entry(record.rep.clone()).or_default().push(record);
        }
    }

    let mut rows = Vec::new();
    for (rep, items) in by_rep {
        let mut customers = HashSet::new();
        let mut revenue_cents = 0;
        for item in &items {
            customers.insert(item.customer_id.clone());
            revenue_cents += item.amount_cents;
        }
        rows.push(RepSummary {
            rep,
            orders: items.len(),
            unique_customers: customers.len(),
            revenue_cents,
        });
    }

    rows.sort_by(|a, b| a.rep.cmp(&b.rep));
    rows
}

pub fn render_report(records: &[SaleRecord], week: u32) -> String {
    let rows = weekly_summary(records, week);
    let mut out = format!("week {}\n", week);
    for row in rows {
        out.push_str(&format!(
            "{} | orders={} | customers={} | revenue={}\n",
            row.rep, row.orders, row.unique_customers, row.revenue_cents
        ));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(week: u32, rep: &str, customer_id: &str, amount_cents: i64, valid: bool) -> SaleRecord {
        SaleRecord {
            week,
            rep: rep.to_string(),
            customer_id: customer_id.to_string(),
            amount_cents,
            valid,
        }
    }

    #[test]
    fn summary_uses_only_valid_positive_sales_for_requested_week() {
        let records = vec![
            s(18, "Ava", "c1", 500, true),
            s(18, "Ava", "c2", 0, true),
            s(18, "Ava", "c3", -50, true),
            s(18, "Ava", "c4", 700, false),
            s(17, "Ava", "c5", 900, true),
            s(18, "Ben", "c6", 300, true),
        ];

        let got = weekly_summary(&records, 18);
        assert_eq!(
            got,
            vec![
                RepSummary {
                    rep: "Ava".to_string(),
                    orders: 1,
                    unique_customers: 1,
                    revenue_cents: 500,
                },
                RepSummary {
                    rep: "Ben".to_string(),
                    orders: 1,
                    unique_customers: 1,
                    revenue_cents: 300,
                },
            ]
        );
    }

    #[test]
    fn duplicate_customer_counts_once_per_rep() {
        let records = vec![
            s(18, "Cara", "dup", 400, true),
            s(18, "Cara", "dup", 250, true),
            s(18, "Cara", "new", 100, true),
        ];

        let got = weekly_summary(&records, 18);
        assert_eq!(got.len(), 1);
        assert_eq!(got[0].orders, 3);
        assert_eq!(got[0].unique_customers, 2);
        assert_eq!(got[0].revenue_cents, 750);
    }

    #[test]
    fn sorting_is_by_revenue_desc_then_customers_desc_then_rep_name() {
        let records = vec![
            s(9, "Mia", "m1", 500, true),
            s(9, "Mia", "m2", 100, true),
            s(9, "Noah", "n1", 600, true),
            s(9, "Liam", "l1", 400, true),
            s(9, "Liam", "l2", 200, true),
        ];

        let got = weekly_summary(&records, 9);
        let reps: Vec<_> = got.iter().map(|r| r.rep.as_str()).collect();
        assert_eq!(reps, vec!["Liam", "Mia", "Noah"]);
    }

    #[test]
    fn render_includes_footer_totals_based_on_summary_rows() {
        let records = vec![
            s(22, "Ava", "c1", 500, true),
            s(22, "Ava", "c1", 200, true),
            s(22, "Ben", "c2", 300, true),
            s(22, "Ben", "c3", 0, true),
            s(22, "Ben", "c4", 100, false),
        ];

        let report = render_report(&records, 22);
        let expected = "week 22\nAva | orders=2 | customers=1 | revenue=700\nBen | orders=1 | customers=1 | revenue=300\nTOTAL | reps=2 | orders=3 | revenue=1000\n";
        assert_eq!(report, expected);
    }
}
