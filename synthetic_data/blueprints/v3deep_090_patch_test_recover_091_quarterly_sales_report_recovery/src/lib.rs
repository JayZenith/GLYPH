#[derive(Clone, Debug)]
pub struct Sale<'a> {
    pub region: &'a str,
    pub quarter: u8,
    pub amount: i32,
    pub refunded: bool,
}

pub fn quarterly_report(sales: &[Sale]) -> String {
    use std::collections::BTreeMap;

    let mut totals: BTreeMap<&str, i32> = BTreeMap::new();
    let mut counts: BTreeMap<&str, usize> = BTreeMap::new();

    for sale in sales {
        if sale.quarter == 0 || sale.quarter > 4 {
            continue;
        }

        *totals.entry(sale.region).or_insert(0) += sale.amount;
        *counts.entry(sale.region).or_insert(0) += 1;
    }

    let mut rows = Vec::new();
    for (region, total) in totals {
        let count = counts.get(region).copied().unwrap_or(0);
        rows.push(format!("{}:{}:{}", region, total, count));
    }

    rows.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn groups_by_region_uses_net_completed_sales_and_sorts_by_total_desc() {
        let sales = [
            Sale { region: "west", quarter: 1, amount: 120, refunded: false },
            Sale { region: "east", quarter: 2, amount: 90, refunded: false },
            Sale { region: "west", quarter: 3, amount: 30, refunded: true },
            Sale { region: "north", quarter: 4, amount: 90, refunded: false },
            Sale { region: "east", quarter: 5, amount: 500, refunded: false },
            Sale { region: "east", quarter: 2, amount: 10, refunded: true },
            Sale { region: "south", quarter: 0, amount: 50, refunded: false },
        ];

        let report = quarterly_report(&sales);
        assert_eq!(report, "west:120:1\neast:90:1\nnorth:90:1");
    }

    #[test]
    fn ties_use_region_name_and_empty_input_reports_no_data() {
        let sales = [
            Sale { region: "beta", quarter: 1, amount: 40, refunded: false },
            Sale { region: "alpha", quarter: 2, amount: 40, refunded: false },
            Sale { region: "beta", quarter: 3, amount: 20, refunded: true },
        ];

        assert_eq!(quarterly_report(&sales), "alpha:40:1\nbeta:40:1");
        assert_eq!(quarterly_report(&[]), "no-data");
    }
}
