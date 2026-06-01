use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Sale<'a> {
    pub month: &'a str,
    pub region: &'a str,
    pub amount: i32,
    pub refunded: bool,
}

pub fn monthly_region_report(sales: &[Sale<'_>]) -> Vec<String> {
    let mut grouped: BTreeMap<&str, (i32, usize)> = BTreeMap::new();

    for sale in sales {
        let entry = grouped.entry(sale.month).or_insert((0, 0));
        entry.0 += sale.amount;
        entry.1 += 1;
    }

    let mut lines = Vec::new();
    for (month, (total, count)) in grouped {
        lines.push(format!("{} total={} orders={}", month, total, count));
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn groups_non_refunded_sales_by_month_then_region() {
        let sales = [
            Sale { month: "2024-01", region: "west", amount: 10, refunded: false },
            Sale { month: "2024-01", region: "east", amount: 15, refunded: false },
            Sale { month: "2024-01", region: "west", amount: 5, refunded: true },
            Sale { month: "2024-02", region: "east", amount: 20, refunded: false },
            Sale { month: "2024-02", region: "east", amount: 7, refunded: false },
            Sale { month: "2024-02", region: "north", amount: 9, refunded: false },
        ];

        assert_eq!(
            monthly_region_report(&sales),
            vec![
                "2024-01 east total=15 orders=1".to_string(),
                "2024-01 west total=10 orders=1".to_string(),
                "2024-02 east total=27 orders=2".to_string(),
                "2024-02 north total=9 orders=1".to_string(),
            ]
        );
    }

    #[test]
    fn omits_zero_total_groups_and_sorts_lexicographically() {
        let sales = [
            Sale { month: "2024-03", region: "beta", amount: 5, refunded: false },
            Sale { month: "2024-03", region: "alpha", amount: 8, refunded: false },
            Sale { month: "2024-03", region: "alpha", amount: -8, refunded: false },
            Sale { month: "2024-03", region: "beta", amount: 4, refunded: true },
            Sale { month: "2024-01", region: "zeta", amount: 2, refunded: false },
        ];

        assert_eq!(
            monthly_region_report(&sales),
            vec![
                "2024-01 zeta total=2 orders=1".to_string(),
                "2024-03 beta total=5 orders=1".to_string(),
            ]
        );
    }
}
