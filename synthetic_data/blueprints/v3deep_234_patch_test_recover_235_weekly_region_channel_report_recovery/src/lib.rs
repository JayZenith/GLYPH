#[derive(Clone, Debug)]
pub struct Sale {
    pub region: &'static str,
    pub channel: &'static str,
    pub amount: i32,
    pub refunded: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub struct RegionSummary {
    pub region: String,
    pub gross: i32,
    pub net: i32,
    pub refunds: usize,
    pub channels: Vec<String>,
}

pub fn summarize(sales: &[Sale]) -> Vec<RegionSummary> {
    let mut rows: Vec<RegionSummary> = Vec::new();

    for sale in sales {
        let idx = rows.iter().position(|r| r.region == sale.region);
        if let Some(i) = idx {
            let row = &mut rows[i];
            row.gross += sale.amount;
            if sale.refunded {
                row.refunds += 1;
                row.net += sale.amount;
            } else {
                row.net += sale.amount;
            }
            row.channels.push(sale.channel.to_string());
        } else {
            rows.push(RegionSummary {
                region: sale.region.to_string(),
                gross: sale.amount,
                net: sale.amount,
                refunds: if sale.refunded { 1 } else { 0 },
                channels: vec![sale.channel.to_string()],
            });
        }
    }

    rows.sort_by(|a, b| a.region.cmp(&b.region));
    rows
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_sales() -> Vec<Sale> {
        vec![
            Sale { region: "west", channel: "web", amount: 120, refunded: false },
            Sale { region: "east", channel: "retail", amount: 200, refunded: false },
            Sale { region: "west", channel: "partner", amount: 40, refunded: true },
            Sale { region: "east", channel: "web", amount: 60, refunded: true },
            Sale { region: "north", channel: "retail", amount: 90, refunded: false },
            Sale { region: "east", channel: "retail", amount: 50, refunded: false },
            Sale { region: "north", channel: "web", amount: 30, refunded: false },
            Sale { region: "west", channel: "web", amount: 10, refunded: false },
        ]
    }

    #[test]
    fn summarizes_by_region_with_net_refunds_and_sorted_channels() {
        let got = summarize(&sample_sales());
        let expected = vec![
            RegionSummary {
                region: "east".to_string(),
                gross: 310,
                net: 190,
                refunds: 1,
                channels: vec!["retail".to_string(), "web".to_string()],
            },
            RegionSummary {
                region: "north".to_string(),
                gross: 120,
                net: 120,
                refunds: 0,
                channels: vec!["retail".to_string(), "web".to_string()],
            },
            RegionSummary {
                region: "west".to_string(),
                gross: 170,
                net: 90,
                refunds: 1,
                channels: vec!["partner".to_string(), "web".to_string()],
            },
        ];
        assert_eq!(got, expected);
    }

    #[test]
    fn empty_input_produces_empty_report() {
        assert!(summarize(&[]).is_empty());
    }

    #[test]
    fn duplicate_channels_are_listed_once_per_region() {
        let got = summarize(&sample_sales());
        let west = got.iter().find(|r| r.region == "west").unwrap();
        assert_eq!(west.channels, vec!["partner".to_string(), "web".to_string()]);
    }
}
