use std::collections::BTreeMap;

#[derive(Debug, Clone)]
pub struct SaleRecord<'a> {
    pub week: &'a str,
    pub seller: &'a str,
    pub region: &'a str,
    pub amount: i32,
    pub valid: bool,
}

pub fn weekly_summary(records: &[SaleRecord<'_>]) -> Vec<String> {
    let mut by_week: BTreeMap<&str, (i32, usize, usize)> = BTreeMap::new();

    for r in records {
        let entry = by_week.entry(r.week).or_insert((0, 0, 0));
        entry.0 += r.amount;
        entry.1 += 1;
        if r.valid {
            entry.2 += 1;
        }
    }

    let mut rows: Vec<_> = by_week
        .into_iter()
        .map(|(week, (amount, sellers, valid_rows))| {
            format!("{} total={} sellers={} valid_rows={}", week, amount, sellers, valid_rows)
        })
        .collect();

    rows.sort();
    rows
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<SaleRecord<'static>> {
        vec![
            SaleRecord { week: "2024-W18", seller: "ann", region: "north", amount: 50, valid: true },
            SaleRecord { week: "2024-W18", seller: "ann", region: "north", amount: 20, valid: true },
            SaleRecord { week: "2024-W18", seller: "bob", region: "south", amount: 40, valid: false },
            SaleRecord { week: "2024-W19", seller: "cyd", region: "east", amount: 70, valid: true },
            SaleRecord { week: "2024-W19", seller: "dan", region: "east", amount: 30, valid: true },
            SaleRecord { week: "2024-W19", seller: "cyd", region: "east", amount: 10, valid: false },
            SaleRecord { week: "2024-W20", seller: "eve", region: "west", amount: 0, valid: true },
            SaleRecord { week: "2024-W20", seller: "fran", region: "west", amount: 15, valid: false },
            SaleRecord { week: "2024-W21", seller: "gary", region: "north", amount: 25, valid: false },
        ]
    }

    #[test]
    fn keeps_only_weeks_with_at_least_one_valid_sale() {
        let rows = weekly_summary(&sample());
        assert_eq!(rows.len(), 3);
        assert!(rows.iter().all(|r| !r.starts_with("2024-W21 ")));
    }

    #[test]
    fn totals_and_unique_sellers_use_only_valid_rows() {
        let rows = weekly_summary(&sample());
        assert_eq!(rows[0], "2024-W19 total=100 sellers=2 valid_rows=2");
        assert_eq!(rows[1], "2024-W18 total=70 sellers=1 valid_rows=2");
        assert_eq!(rows[2], "2024-W20 total=0 sellers=1 valid_rows=1");
    }

    #[test]
    fn rows_sorted_by_total_desc_then_week_asc() {
        let rows = weekly_summary(&sample());
        assert_eq!(
            rows,
            vec![
                "2024-W19 total=100 sellers=2 valid_rows=2",
                "2024-W18 total=70 sellers=1 valid_rows=2",
                "2024-W20 total=0 sellers=1 valid_rows=1",
            ]
        );
    }

    #[test]
    fn duplicate_valid_rows_do_not_inflate_unique_seller_count() {
        let rows = weekly_summary(&sample());
        let w18 = rows.into_iter().find(|r| r.starts_with("2024-W18 ")).unwrap();
        assert!(w18.contains("sellers=1"));
    }

    #[test]
    fn tie_on_total_uses_week_ascending() {
        let records = vec![
            SaleRecord { week: "2024-W10", seller: "a", region: "n", amount: 25, valid: true },
            SaleRecord { week: "2024-W11", seller: "b", region: "n", amount: 25, valid: true },
            SaleRecord { week: "2024-W09", seller: "c", region: "n", amount: 10, valid: true },
        ];
        let rows = weekly_summary(&records);
        assert_eq!(
            rows,
            vec![
                "2024-W10 total=25 sellers=1 valid_rows=1",
                "2024-W11 total=25 sellers=1 valid_rows=1",
                "2024-W09 total=10 sellers=1 valid_rows=1",
            ]
        );
    }
}
