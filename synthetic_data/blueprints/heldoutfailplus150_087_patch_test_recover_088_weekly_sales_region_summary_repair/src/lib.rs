use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct SaleRecord {
    pub week: u32,
    pub region: String,
    pub rep_id: String,
    pub amount_cents: i64,
    pub valid: bool,
}

#[derive(Default, Debug)]
struct RegionAgg {
    gross_cents: i64,
    order_count: usize,
    reps: Vec<String>,
}

pub fn weekly_region_report(records: &[SaleRecord], week: u32) -> String {
    let mut by_region: BTreeMap<String, RegionAgg> = BTreeMap::new();

    for r in records {
        if r.week != week {
            continue;
        }

        let agg = by_region.entry(r.region.clone()).or_default();
        agg.gross_cents += r.amount_cents;
        agg.order_count += 1;
        agg.reps.push(r.rep_id.clone());
    }

    let mut rows: Vec<(String, RegionAgg)> = by_region.into_iter().collect();
    rows.sort_by(|a, b| a.0.cmp(&b.0));

    let mut out = format!("WEEK {} SUMMARY", week);
    for (region, agg) in rows {
        out.push_str(&format!(
            "\n{} | orders={} | reps={} | gross=${:.2}",
            region,
            agg.order_count,
            agg.reps.len(),
            agg.gross_cents as f64 / 100.0
        ));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(week: u32, region: &str, rep: &str, amount_cents: i64, valid: bool) -> SaleRecord {
        SaleRecord {
            week,
            region: region.to_string(),
            rep_id: rep.to_string(),
            amount_cents,
            valid,
        }
    }

    #[test]
    fn report_filters_invalid_and_ignores_nonpositive_and_empty_region() {
        let records = vec![
            rec(12, "West", "r1", 1250, true),
            rec(12, "West", "r2", 0, true),
            rec(12, "West", "r3", -50, true),
            rec(12, "West", "r4", 800, false),
            rec(12, "", "r9", 500, true),
            rec(11, "West", "old", 9999, true),
        ];

        let got = weekly_region_report(&records, 12);
        let want = "WEEK 12 SUMMARY\nWest | orders=1 | reps=1 | gross=$12.50";
        assert_eq!(got, want);
    }

    #[test]
    fn report_counts_unique_reps_per_region() {
        let records = vec![
            rec(7, "North", "amy", 1000, true),
            rec(7, "North", "amy", 250, true),
            rec(7, "North", "ben", 500, true),
            rec(7, "North", "ben", 700, false),
        ];

        let got = weekly_region_report(&records, 7);
        let want = "WEEK 7 SUMMARY\nNorth | orders=3 | reps=2 | gross=$17.50";
        assert_eq!(got, want);
    }

    #[test]
    fn report_sorts_by_gross_desc_then_region_asc() {
        let records = vec![
            rec(20, "South", "s1", 1000, true),
            rec(20, "East", "e1", 2000, true),
            rec(20, "West", "w1", 2000, true),
            rec(20, "North", "n1", 500, true),
        ];

        let got = weekly_region_report(&records, 20);
        let want = "WEEK 20 SUMMARY\nEast | orders=1 | reps=1 | gross=$20.00\nWest | orders=1 | reps=1 | gross=$20.00\nSouth | orders=1 | reps=1 | gross=$10.00\nNorth | orders=1 | reps=1 | gross=$5.00";
        assert_eq!(got, want);
    }

    #[test]
    fn report_skips_regions_with_no_valid_sales_after_filtering() {
        let records = vec![
            rec(4, "Ghost", "g1", 0, true),
            rec(4, "Ghost", "g2", -10, true),
            rec(4, "Ghost", "g3", 99, false),
            rec(4, "Live", "l1", 300, true),
        ];

        let got = weekly_region_report(&records, 4);
        let want = "WEEK 4 SUMMARY\nLive | orders=1 | reps=1 | gross=$3.00";
        assert_eq!(got, want);
    }
}
