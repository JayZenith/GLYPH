use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct Record {
    pub month: &'static str,
    pub category: &'static str,
    pub amount: i32,
    pub refunded: bool,
}

pub fn monthly_report(records: &[Record]) -> String {
    let mut grouped: BTreeMap<&str, (i32, usize, usize)> = BTreeMap::new();

    for r in records {
        let entry = grouped.entry(r.month).or_insert((0, 0, 0));
        entry.0 += r.amount;
        entry.1 += 1;
        if r.refunded {
            entry.2 += 1;
        }
    }

    let mut out = String::new();
    for (month, (net, count, refunds)) in grouped {
        out.push_str(&format!("{}: net={} count={} refunds={}\n", month, net, count, refunds));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Record> {
        vec![
            Record { month: "2024-01", category: "books", amount: 30, refunded: false },
            Record { month: "2024-01", category: "games", amount: 20, refunded: true },
            Record { month: "2024-01", category: "books", amount: 10, refunded: false },
            Record { month: "2024-02", category: "books", amount: 15, refunded: false },
            Record { month: "2024-02", category: "garden", amount: 50, refunded: true },
            Record { month: "2024-02", category: "garden", amount: 25, refunded: false },
            Record { month: "2024-03", category: "books", amount: 40, refunded: true },
        ]
    }

    #[test]
    fn groups_by_month_and_sorts_categories() {
        let got = monthly_report(&sample());
        let expected = concat!(
            "2024-01: net=20 count=3 refunds=1 categories=books|games\n",
            "2024-02: net=-10 count=3 refunds=1 categories=books|garden\n",
            "2024-03: net=-40 count=1 refunds=1 categories=books\n",
        );
        assert_eq!(got, expected);
    }

    #[test]
    fn skips_zero_only_months_after_refunds() {
        let records = vec![
            Record { month: "2024-04", category: "misc", amount: 10, refunded: false },
            Record { month: "2024-04", category: "misc", amount: 10, refunded: true },
            Record { month: "2024-05", category: "tools", amount: 7, refunded: false },
        ];
        let expected = "2024-05: net=7 count=1 refunds=0 categories=tools\n";
        assert_eq!(monthly_report(&records), expected);
    }

    #[test]
    fn empty_input_yields_empty_report() {
        assert_eq!(monthly_report(&[]), "");
    }
}
