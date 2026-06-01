#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Sale {
    pub region: &'static str,
    pub rep: &'static str,
    pub amount: i32,
    pub refunded: bool,
}

pub fn build_report(sales: &[Sale]) -> String {
    let mut rows: Vec<(&str, i32, usize)> = Vec::new();

    for sale in sales {
        let amt = sale.amount;
        if let Some(row) = rows.iter_mut().find(|row| row.0 == sale.region) {
            row.1 += amt;
            row.2 += 1;
        } else {
            rows.push((sale.region, amt, 1));
        }
    }

    rows.sort_by(|a, b| a.0.cmp(b.0));

    let mut out = String::new();
    let grand_total: i32 = rows.iter().map(|row| row.1).sum();
    out.push_str(&format!("Grand total: {}\n", grand_total));

    for (region, total, count) in rows {
        out.push_str(&format!("{} => total={}, count={}\n", region, total, count));
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_sales() -> Vec<Sale> {
        vec![
            Sale { region: "West", rep: "Ava", amount: 120, refunded: false },
            Sale { region: "East", rep: "Ben", amount: 90, refunded: true },
            Sale { region: "West", rep: "Cara", amount: 40, refunded: false },
            Sale { region: "North", rep: "Dan", amount: 70, refunded: false },
            Sale { region: "East", rep: "Eli", amount: 30, refunded: false },
            Sale { region: "West", rep: "Ava", amount: 10, refunded: true },
            Sale { region: "North", rep: "Fay", amount: 20, refunded: false },
        ]
    }

    #[test]
    fn skips_refunds_and_sorts_by_total_desc_then_region() {
        let report = build_report(&sample_sales());
        let expected = concat!(
            "Grand total: 280\n",
            "West => total=160, count=2\n",
            "North => total=90, count=2\n",
            "East => total=30, count=1\n"
        );
        assert_eq!(report, expected);
    }

    #[test]
    fn excludes_regions_with_no_kept_sales() {
        let sales = vec![
            Sale { region: "South", rep: "Gus", amount: 50, refunded: true },
            Sale { region: "East", rep: "Hal", amount: 20, refunded: false },
        ];
        let expected = concat!(
            "Grand total: 20\n",
            "East => total=20, count=1\n"
        );
        assert_eq!(build_report(&sales), expected);
    }

    #[test]
    fn uses_unique_rep_count_per_region() {
        let sales = vec![
            Sale { region: "Central", rep: "Ivy", amount: 10, refunded: false },
            Sale { region: "Central", rep: "Ivy", amount: 15, refunded: false },
            Sale { region: "Central", rep: "Jay", amount: 5, refunded: false },
        ];
        let expected = concat!(
            "Grand total: 30\n",
            "Central => total=30, count=2\n"
        );
        assert_eq!(build_report(&sales), expected);
    }

    #[test]
    fn tie_on_total_uses_region_name() {
        let sales = vec![
            Sale { region: "Beta", rep: "Kim", amount: 40, refunded: false },
            Sale { region: "Alpha", rep: "Lee", amount: 40, refunded: false },
        ];
        let expected = concat!(
            "Grand total: 80\n",
            "Alpha => total=40, count=1\n",
            "Beta => total=40, count=1\n"
        );
        assert_eq!(build_report(&sales), expected);
    }
}
