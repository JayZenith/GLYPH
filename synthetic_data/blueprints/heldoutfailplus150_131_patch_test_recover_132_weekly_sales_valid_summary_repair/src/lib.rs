use std::collections::{BTreeSet, HashMap};

#[derive(Clone, Debug)]
pub struct SaleRecord {
    pub week: u32,
    pub region: String,
    pub rep_id: u32,
    pub order_id: String,
    pub amount_cents: i64,
    pub valid: bool,
}

pub fn weekly_region_report(records: &[SaleRecord], week: u32) -> Vec<String> {
    let mut totals: HashMap<String, (i64, usize, usize)> = HashMap::new();

    for r in records {
        if r.week != week {
            continue;
        }

        let entry = totals.entry(r.region.clone()).or_insert((0, 0, 0));
        entry.0 += r.amount_cents;
        entry.1 += 1;
        entry.2 += 1;
    }

    let mut rows: Vec<(String, i64, usize, usize)> = totals
        .into_iter()
        .map(|(region, (amount, orders, reps))| (region, amount, orders, reps))
        .collect();

    rows.sort_by(|a, b| a.0.cmp(&b.0));

    rows.into_iter()
        .map(|(region, amount, orders, reps)| {
            format!("{}|orders={}|reps={}|sales=${:.2}", region, orders, reps, amount as f64 / 100.0)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(week: u32, region: &str, rep_id: u32, order_id: &str, amount_cents: i64, valid: bool) -> SaleRecord {
        SaleRecord {
            week,
            region: region.to_string(),
            rep_id,
            order_id: order_id.to_string(),
            amount_cents,
            valid,
        }
    }

    #[test]
    fn filters_invalid_and_other_weeks() {
        let rows = weekly_region_report(
            &[
                rec(7, "West", 10, "A1", 1200, true),
                rec(7, "West", 10, "A2", 800, false),
                rec(8, "West", 10, "A3", 900, true),
                rec(7, "East", 20, "E1", 500, true),
            ],
            7,
        );

        assert_eq!(
            rows,
            vec![
                "West|orders=1|reps=1|sales=$12.00".to_string(),
                "East|orders=1|reps=1|sales=$5.00".to_string(),
            ]
        );
    }

    #[test]
    fn counts_unique_reps_and_unique_orders_per_region() {
        let rows = weekly_region_report(
            &[
                rec(3, "North", 7, "N-1", 1000, true),
                rec(3, "North", 7, "N-1", 1000, true),
                rec(3, "North", 7, "N-2", 500, true),
                rec(3, "North", 8, "N-3", 700, true),
                rec(3, "South", 9, "S-1", 250, true),
            ],
            3,
        );

        assert_eq!(
            rows,
            vec![
                "North|orders=3|reps=2|sales=$22.00".to_string(),
                "South|orders=1|reps=1|sales=$2.50".to_string(),
            ]
        );
    }

    #[test]
    fn sorts_by_sales_desc_then_orders_desc_then_region() {
        let rows = weekly_region_report(
            &[
                rec(5, "Gamma", 1, "G1", 1000, true),
                rec(5, "Alpha", 2, "A1", 700, true),
                rec(5, "Alpha", 3, "A2", 300, true),
                rec(5, "Beta", 4, "B1", 600, true),
                rec(5, "Beta", 5, "B2", 400, true),
                rec(5, "Beta", 5, "B3", 0, true),
                rec(5, "Delta", 6, "D1", 1000, true),
            ],
            5,
        );

        assert_eq!(
            rows,
            vec![
                "Beta|orders=3|reps=2|sales=$10.00".to_string(),
                "Alpha|orders=2|reps=2|sales=$10.00".to_string(),
                "Delta|orders=1|reps=1|sales=$10.00".to_string(),
                "Gamma|orders=1|reps=1|sales=$10.00".to_string(),
            ]
        );
    }

    #[test]
    fn excludes_non_positive_valid_sales() {
        let rows = weekly_region_report(
            &[
                rec(9, "Central", 1, "C1", 0, true),
                rec(9, "Central", 2, "C2", -50, true),
                rec(9, "Central", 3, "C3", 125, true),
                rec(9, "Coastal", 4, "K1", -10, false),
                rec(9, "Coastal", 4, "K2", 200, true),
            ],
            9,
        );

        assert_eq!(
            rows,
            vec![
                "Coastal|orders=1|reps=1|sales=$2.00".to_string(),
                "Central|orders=1|reps=1|sales=$1.25".to_string(),
            ]
        );
    }

    #[test]
    fn drops_regions_with_no_remaining_valid_orders() {
        let rows = weekly_region_report(
            &[
                rec(11, "North", 1, "N1", 0, true),
                rec(11, "North", 2, "N2", -100, true),
                rec(11, "South", 3, "S1", 300, true),
                rec(11, "South", 3, "S2", 200, false),
            ],
            11,
        );

        assert_eq!(rows, vec!["South|orders=1|reps=1|sales=$3.00".to_string()]);
    }

    #[test]
    fn returns_empty_when_week_has_no_valid_orders() {
        let rows = weekly_region_report(
            &[
                rec(20, "East", 1, "E1", 0, true),
                rec(20, "East", 2, "E2", 100, false),
                rec(21, "West", 3, "W1", 500, true),
            ],
            20,
        );

        assert!(rows.is_empty());
    }
}
