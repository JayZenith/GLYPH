use std::collections::{BTreeMap, HashSet};

#[derive(Debug, Clone)]
pub struct SaleRecord {
    pub week: &'static str,
    pub rep: &'static str,
    pub customer_id: &'static str,
    pub amount_cents: i64,
    pub status: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WeeklySummary {
    pub week: String,
    pub total_cents: i64,
    pub valid_sales: usize,
    pub unique_customers: usize,
}

pub fn build_weekly_report(rows: &[SaleRecord]) -> String {
    let mut grouped: BTreeMap<&str, (i64, usize, usize)> = BTreeMap::new();

    for row in rows {
        let entry = grouped.entry(row.week).or_insert((0, 0, 0));
        entry.0 += row.amount_cents;
        entry.1 += 1;
        entry.2 += 1;
    }

    let mut summaries: Vec<WeeklySummary> = grouped
        .into_iter()
        .map(|(week, (total_cents, valid_sales, unique_customers))| WeeklySummary {
            week: week.to_string(),
            total_cents,
            valid_sales,
            unique_customers,
        })
        .collect();

    summaries.sort_by(|a, b| a.week.cmp(&b.week));

    let mut out = vec!["week,total_cents,valid_sales,unique_customers".to_string()];
    for s in summaries {
        out.push(format!(
            "{},{},{},{}",
            s.week, s.total_cents, s.valid_sales, s.unique_customers
        ));
    }
    out.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_rows() -> Vec<SaleRecord> {
        vec![
            SaleRecord { week: "2024-W02", rep: "Ana", customer_id: "C1", amount_cents: 1200, status: "paid" },
            SaleRecord { week: "2024-W02", rep: "Ana", customer_id: "C1", amount_cents: 800, status: "paid" },
            SaleRecord { week: "2024-W02", rep: "Bo", customer_id: "C2", amount_cents: 500, status: "pending" },
            SaleRecord { week: "2024-W02", rep: "Cy", customer_id: "C3", amount_cents: 0, status: "paid" },
            SaleRecord { week: "2024-W01", rep: "Ana", customer_id: "C9", amount_cents: 700, status: "paid" },
            SaleRecord { week: "2024-W01", rep: "Bo", customer_id: "C8", amount_cents: -50, status: "paid" },
            SaleRecord { week: "2024-W01", rep: "Bo", customer_id: "C7", amount_cents: 900, status: "refunded" },
            SaleRecord { week: "2024-W03", rep: "Di", customer_id: "C5", amount_cents: 300, status: "paid" },
            SaleRecord { week: "2024-W03", rep: "Di", customer_id: "C6", amount_cents: 300, status: "paid" },
            SaleRecord { week: "2024-W03", rep: "Eli", customer_id: "C5", amount_cents: 400, status: "paid" },
            SaleRecord { week: "2024-W04", rep: "Fox", customer_id: "C10", amount_cents: 0, status: "pending" },
        ]
    }

    #[test]
    fn report_filters_invalid_rows_and_uses_unique_customers() {
        let got = build_weekly_report(&sample_rows());
        let expected = [
            "week,total_cents,valid_sales,unique_customers",
            "2024-W03,1000,3,2",
            "2024-W02,2000,2,1",
            "2024-W01,700,1,1",
        ]
        .join("\n");
        assert_eq!(got, expected);
    }

    #[test]
    fn excludes_weeks_without_any_valid_sales() {
        let rows = vec![
            SaleRecord { week: "2024-W09", rep: "A", customer_id: "X", amount_cents: 0, status: "paid" },
            SaleRecord { week: "2024-W09", rep: "A", customer_id: "Y", amount_cents: 50, status: "pending" },
            SaleRecord { week: "2024-W10", rep: "B", customer_id: "Z", amount_cents: 75, status: "paid" },
        ];
        let got = build_weekly_report(&rows);
        let expected = [
            "week,total_cents,valid_sales,unique_customers",
            "2024-W10,75,1,1",
        ]
        .join("\n");
        assert_eq!(got, expected);
    }

    #[test]
    fn sorts_by_total_desc_then_week_asc() {
        let rows = vec![
            SaleRecord { week: "2024-W05", rep: "A", customer_id: "U1", amount_cents: 500, status: "paid" },
            SaleRecord { week: "2024-W04", rep: "A", customer_id: "U2", amount_cents: 500, status: "paid" },
            SaleRecord { week: "2024-W06", rep: "A", customer_id: "U3", amount_cents: 300, status: "paid" },
        ];
        let got = build_weekly_report(&rows);
        let expected = [
            "week,total_cents,valid_sales,unique_customers",
            "2024-W04,500,1,1",
            "2024-W05,500,1,1",
            "2024-W06,300,1,1",
        ]
        .join("\n");
        assert_eq!(got, expected);
    }

    #[test]
    fn duplicate_customers_within_week_count_once_even_across_reps() {
        let rows = vec![
            SaleRecord { week: "2024-W11", rep: "A", customer_id: "Q1", amount_cents: 200, status: "paid" },
            SaleRecord { week: "2024-W11", rep: "B", customer_id: "Q1", amount_cents: 300, status: "paid" },
            SaleRecord { week: "2024-W11", rep: "C", customer_id: "Q2", amount_cents: 100, status: "paid" },
        ];
        let got = build_weekly_report(&rows);
        let expected = [
            "week,total_cents,valid_sales,unique_customers",
            "2024-W11,600,3,2",
        ]
        .join("\n");
        assert_eq!(got, expected);
    }
}
