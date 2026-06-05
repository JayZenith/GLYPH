use std::collections::BTreeMap;

#[derive(Debug, Clone)]
pub struct Sale {
    pub week: u32,
    pub region: String,
    pub rep_id: u32,
    pub amount_cents: i64,
    pub refunded: bool,
    pub verified: bool,
}

pub fn weekly_region_report(sales: &[Sale], week: u32) -> String {
    let mut groups: BTreeMap<String, (i64, usize, usize)> = BTreeMap::new();

    for sale in sales {
        if sale.week != week {
            continue;
        }
        if sale.amount_cents <= 0 {
            continue;
        }

        let entry = groups
            .entry(sale.region.clone())
            .or_insert((0, 0, 0));
        entry.0 += sale.amount_cents;
        entry.1 += 1;
        entry.2 += 1;
    }

    let mut rows: Vec<(String, i64, usize, usize)> = groups
        .into_iter()
        .map(|(region, (revenue, orders, reps))| (region, revenue, orders, reps))
        .collect();

    rows.sort_by(|a, b| a.0.cmp(&b.0));

    let mut out = format!("WEEK {} SUMMARY", week);
    for (region, revenue, orders, reps) in rows {
        out.push_str(&format!("\n{} | orders={} | reps={} | revenue=${:.2}", region, orders, reps, revenue as f64 / 100.0));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(week: u32, region: &str, rep_id: u32, amount_cents: i64, refunded: bool, verified: bool) -> Sale {
        Sale {
            week,
            region: region.to_string(),
            rep_id,
            amount_cents,
            refunded,
            verified,
        }
    }

    #[test]
    fn filters_invalid_rows_before_grouping() {
        let sales = vec![
            s(8, "North", 1, 1200, false, true),
            s(8, "North", 2, 800, true, true),
            s(8, "North", 3, 500, false, false),
            s(8, "North", 4, 0, false, true),
            s(7, "North", 5, 9999, false, true),
        ];

        let expected = "WEEK 8 SUMMARY\nNorth | orders=1 | reps=1 | revenue=$12.00";
        assert_eq!(weekly_region_report(&sales, 8), expected);
    }

    #[test]
    fn counts_unique_reps_within_each_region() {
        let sales = vec![
            s(3, "West", 10, 1000, false, true),
            s(3, "West", 10, 1500, false, true),
            s(3, "West", 11, 700, false, true),
            s(3, "East", 10, 400, false, true),
        ];

        let expected = "WEEK 3 SUMMARY\nWest | orders=3 | reps=2 | revenue=$32.00\nEast | orders=1 | reps=1 | revenue=$4.00";
        assert_eq!(weekly_region_report(&sales, 3), expected);
    }

    #[test]
    fn sorts_by_revenue_desc_then_region_name() {
        let sales = vec![
            s(4, "Delta", 1, 1200, false, true),
            s(4, "Bravo", 2, 1200, false, true),
            s(4, "Alpha", 3, 2400, false, true),
            s(4, "Echo", 4, 500, false, true),
        ];

        let expected = "WEEK 4 SUMMARY\nAlpha | orders=1 | reps=1 | revenue=$24.00\nBravo | orders=1 | reps=1 | revenue=$12.00\nDelta | orders=1 | reps=1 | revenue=$12.00\nEcho | orders=1 | reps=1 | revenue=$5.00";
        assert_eq!(weekly_region_report(&sales, 4), expected);
    }

    #[test]
    fn omits_empty_report_rows_and_formats_no_data_case() {
        let sales = vec![
            s(9, "South", 1, 1000, true, true),
            s(9, "South", 2, 800, false, false),
            s(8, "South", 3, 900, false, true),
        ];

        assert_eq!(weekly_region_report(&sales, 9), "WEEK 9 SUMMARY\n(no valid sales)");
    }
}
