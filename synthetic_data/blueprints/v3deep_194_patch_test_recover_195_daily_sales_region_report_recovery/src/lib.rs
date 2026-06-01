use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Sale {
    pub region: &'static str,
    pub amount_cents: u32,
    pub refunded: bool,
}

pub fn sales_report(sales: &[Sale]) -> String {
    let mut totals: BTreeMap<&str, u32> = BTreeMap::new();

    for sale in sales {
        *totals.entry(sale.region).or_insert(0) += sale.amount_cents;
    }

    let mut out = String::new();
    for (region, total) in totals {
        out.push_str(&format!("{}:${}.{:02}\n", region, total / 100, total % 100));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::{sales_report, Sale};

    #[test]
    fn groups_non_refunded_sales_and_sorts_by_total_desc_then_region() {
        let sales = [
            Sale { region: "west", amount_cents: 500, refunded: false },
            Sale { region: "east", amount_cents: 800, refunded: true },
            Sale { region: "north", amount_cents: 300, refunded: false },
            Sale { region: "west", amount_cents: 250, refunded: false },
            Sale { region: "east", amount_cents: 200, refunded: false },
            Sale { region: "south", amount_cents: 750, refunded: false },
        ];

        let report = sales_report(&sales);
        assert_eq!(report, "south:$7.50\nwest:$7.50\nnorth:$3.00\neast:$2.00\nTOTAL:$20.00");
    }

    #[test]
    fn omits_empty_input_and_zero_totals_but_still_reports_total() {
        let sales = [
            Sale { region: "west", amount_cents: 0, refunded: false },
            Sale { region: "east", amount_cents: 125, refunded: true },
        ];

        let report = sales_report(&sales);
        assert_eq!(report, "TOTAL:$0.00");
    }
}
