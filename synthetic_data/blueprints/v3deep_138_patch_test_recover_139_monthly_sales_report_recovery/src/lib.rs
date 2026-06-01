use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Sale<'a> {
    pub rep: &'a str,
    pub region: &'a str,
    pub amount: i32,
    pub refunded: bool,
}

pub fn sales_report(sales: &[Sale<'_>]) -> String {
    let mut totals: BTreeMap<&str, (i32, usize)> = BTreeMap::new();

    for sale in sales {
        let entry = totals.entry(sale.rep).or_insert((0, 0));
        entry.0 += sale.amount;
        entry.1 += 1;
    }

    let mut out = String::new();
    for (rep, (amount, count)) in totals {
        out.push_str(&format!("{}|{}|{}\n", rep, count, amount));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Sale<'static>> {
        vec![
            Sale { rep: "Ava", region: "East", amount: 120, refunded: false },
            Sale { rep: "Ben", region: "West", amount: 75, refunded: false },
            Sale { rep: "Ava", region: "East", amount: 40, refunded: true },
            Sale { rep: "Ava", region: "North", amount: 30, refunded: false },
            Sale { rep: "Ben", region: "West", amount: 25, refunded: true },
            Sale { rep: "Cara", region: "South", amount: 90, refunded: false },
            Sale { rep: "Cara", region: "South", amount: 10, refunded: false },
            Sale { rep: "Dan", region: "East", amount: 0, refunded: false },
        ]
    }

    #[test]
    fn report_groups_active_sales_only_and_sorts_by_total_desc_then_name() {
        let report = sales_report(&sample());
        let expected = "Ava|2|150|East,North\nCara|2|100|South\nBen|1|75|West\nDan|1|0|East\nTOTAL|4|325\n";
        assert_eq!(report, expected);
    }

    #[test]
    fn empty_input_returns_just_total_line() {
        assert_eq!(sales_report(&[]), "TOTAL|0|0\n");
    }
}
