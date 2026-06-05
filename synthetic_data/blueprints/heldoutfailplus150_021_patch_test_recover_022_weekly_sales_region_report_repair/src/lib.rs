use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub struct SaleRecord {
    pub week: u32,
    pub region: String,
    pub rep_id: u32,
    pub amount: i64,
    pub refunded: bool,
    pub approved: bool,
}

pub fn weekly_region_report(records: &[SaleRecord], week: u32) -> Vec<String> {
    let mut by_region: BTreeMap<String, (i64, usize, usize)> = BTreeMap::new();

    for r in records {
        if r.week != week {
            continue;
        }
        let entry = by_region.entry(r.region.clone()).or_insert((0, 0, 0));
        entry.0 += r.amount;
        entry.1 += 1;
        entry.2 += 1;
    }

    let mut rows: Vec<_> = by_region.into_iter().collect();
    rows.sort_by(|a, b| a.0.cmp(&b.0));

    rows
        .into_iter()
        .map(|(region, (total, orders, reps))| {
            format!("{} | orders={} | reps={} | total={}", region, orders, reps, total)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(
        week: u32,
        region: &str,
        rep_id: u32,
        amount: i64,
        refunded: bool,
        approved: bool,
    ) -> SaleRecord {
        SaleRecord {
            week,
            region: region.to_string(),
            rep_id,
            amount,
            refunded,
            approved,
        }
    }

    #[test]
    fn report_only_uses_valid_records_for_target_week() {
        let rows = weekly_region_report(
            &[
                rec(18, "North", 1, 120, false, true),
                rec(18, "North", 2, 80, true, true),
                rec(18, "North", 3, 50, false, false),
                rec(19, "North", 4, 999, false, true),
                rec(18, "South", 5, 70, false, true),
            ],
            18,
        );

        assert_eq!(
            rows,
            vec![
                "South | orders=1 | reps=1 | total=70",
                "North | orders=1 | reps=1 | total=120",
            ]
        );
    }

    #[test]
    fn report_counts_unique_reps_per_region() {
        let rows = weekly_region_report(
            &[
                rec(7, "West", 10, 40, false, true),
                rec(7, "West", 10, 15, false, true),
                rec(7, "West", 11, 25, false, true),
            ],
            7,
        );

        assert_eq!(rows, vec!["West | orders=3 | reps=2 | total=80"]);
    }

    #[test]
    fn report_sorts_by_total_desc_then_region_asc() {
        let rows = weekly_region_report(
            &[
                rec(3, "Gamma", 1, 50, false, true),
                rec(3, "Alpha", 2, 70, false, true),
                rec(3, "Beta", 3, 70, false, true),
                rec(3, "Delta", 4, 10, false, true),
            ],
            3,
        );

        assert_eq!(
            rows,
            vec![
                "Alpha | orders=1 | reps=1 | total=70",
                "Beta | orders=1 | reps=1 | total=70",
                "Gamma | orders=1 | reps=1 | total=50",
                "Delta | orders=1 | reps=1 | total=10",
            ]
        );
    }

    #[test]
    fn report_omits_regions_with_no_valid_sales() {
        let rows = weekly_region_report(
            &[
                rec(11, "Empty", 1, 20, true, true),
                rec(11, "Empty", 2, 30, false, false),
                rec(11, "Live", 3, 25, false, true),
            ],
            11,
        );

        assert_eq!(rows, vec!["Live | orders=1 | reps=1 | total=25"]);
    }

    #[test]
    fn report_keeps_negative_valid_totals_in_sorting() {
        let rows = weekly_region_report(
            &[
                rec(5, "North", 1, -10, false, true),
                rec(5, "South", 2, 5, false, true),
                rec(5, "East", 3, 0, false, true),
            ],
            5,
        );

        assert_eq!(
            rows,
            vec![
                "South | orders=1 | reps=1 | total=5",
                "East | orders=1 | reps=1 | total=0",
                "North | orders=1 | reps=1 | total=-10",
            ]
        );
    }
}
