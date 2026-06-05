use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone)]
pub struct SaleRecord<'a> {
    pub week: u32,
    pub region: &'a str,
    pub rep_id: &'a str,
    pub order_id: &'a str,
    pub amount_cents: i64,
    pub status: &'a str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegionSummary {
    pub region: String,
    pub total_cents: i64,
    pub valid_orders: usize,
    pub unique_reps: usize,
}

pub fn summarize_week(records: &[SaleRecord], week: u32) -> Vec<RegionSummary> {
    let mut totals: HashMap<String, i64> = HashMap::new();
    let mut orders: HashMap<String, usize> = HashMap::new();
    let mut reps: HashMap<String, HashSet<String>> = HashMap::new();

    for r in records {
        if r.week != week {
            continue;
        }
        if r.status == "cancelled" {
            continue;
        }

        *totals.entry(r.region.to_string()).or_insert(0) += r.amount_cents;
        *orders.entry(r.region.to_string()).or_insert(0) += 1;
        reps.entry(r.region.to_string())
            .or_default()
            .insert(r.rep_id.to_string());
    }

    let mut out: Vec<RegionSummary> = totals
        .into_iter()
        .map(|(region, total_cents)| RegionSummary {
            valid_orders: orders.get(&region).copied().unwrap_or(0),
            unique_reps: reps.get(&region).map(|s| s.len()).unwrap_or(0),
            region,
            total_cents,
        })
        .collect();

    out.sort_by(|a, b| a.region.cmp(&b.region));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec<'a>(
        week: u32,
        region: &'a str,
        rep_id: &'a str,
        order_id: &'a str,
        amount_cents: i64,
        status: &'a str,
    ) -> SaleRecord<'a> {
        SaleRecord {
            week,
            region,
            rep_id,
            order_id,
            amount_cents,
            status,
        }
    }

    #[test]
    fn ignores_invalid_records_and_dedupes_orders_within_region() {
        let rows = vec![
            rec(12, "West", "amy", "W1", 1000, "paid"),
            rec(12, "West", "amy", "W1", 1000, "paid"),
            rec(12, "West", "bob", "W2", 2000, "pending"),
            rec(12, "West", "carl", "W3", -50, "paid"),
            rec(12, "West", "dina", "", 700, "paid"),
            rec(12, "West", "erin", "W4", 900, "refunded"),
            rec(11, "West", "fred", "OLD", 5000, "paid"),
        ];

        let got = summarize_week(&rows, 12);
        assert_eq!(
            got,
            vec![RegionSummary {
                region: "West".to_string(),
                total_cents: 3000,
                valid_orders: 2,
                unique_reps: 2,
            }]
        );
    }

    #[test]
    fn counts_unique_reps_only_from_valid_deduped_orders() {
        let rows = vec![
            rec(8, "North", "r1", "N1", 500, "paid"),
            rec(8, "North", "r1", "N1", 500, "paid"),
            rec(8, "North", "r2", "N2", 700, "pending"),
            rec(8, "North", "r3", "N3", 800, "cancelled"),
            rec(8, "North", "r4", "N4", 0, "paid"),
        ];

        let got = summarize_week(&rows, 8);
        assert_eq!(got.len(), 1);
        assert_eq!(got[0].unique_reps, 2);
        assert_eq!(got[0].valid_orders, 2);
        assert_eq!(got[0].total_cents, 1200);
    }

    #[test]
    fn sorts_by_total_desc_then_region_asc_and_skips_empty_regions() {
        let rows = vec![
            rec(20, "South", "s1", "S1", 1500, "paid"),
            rec(20, "East", "e1", "E1", 1500, "paid"),
            rec(20, "East", "e2", "E2", 300, "pending"),
            rec(20, "North", "n1", "N1", 900, "paid"),
            rec(20, "", "x1", "X1", 4000, "paid"),
            rec(20, "South", "s2", "S2", 100, "refunded"),
        ];

        let got = summarize_week(&rows, 20);
        let regions: Vec<_> = got.iter().map(|r| r.region.as_str()).collect();
        assert_eq!(regions, vec!["East", "South", "North"]);
        assert_eq!(got[0].total_cents, 1800);
        assert_eq!(got[1].total_cents, 1500);
        assert_eq!(got[2].total_cents, 900);
    }
}
