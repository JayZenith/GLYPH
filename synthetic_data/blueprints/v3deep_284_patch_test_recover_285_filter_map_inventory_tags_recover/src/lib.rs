pub fn collect_active_codes(lines: &[&str]) -> Vec<String> {
    lines
        .iter()
        .filter_map(|line| {
            let (id, status, qty, tag) = line.split_once('|')?;
            if status != "active" {
                return None;
            }
            let qty: u32 = qty.parse().ok()?;
            if qty == 0 {
                return None;
            }
            if tag.is_empty() {
                return None;
            }
            Some(format!("{}:{}:{}", id, tag, qty))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_active_codes;

    #[test]
    fn keeps_only_active_positive_and_normalized_entries() {
        let input = [
            "sku1|active|5|blue",
            "sku2|inactive|3|green",
            "sku3|active|0|orange",
            "sku4|active|2|  red  ",
            "sku5|ACTIVE|4|silver",
            "sku6|active|9|clearance",
            "sku7|active|2|",
            "sku8|active|7| blue ",
        ];

        let got = collect_active_codes(&input);
        assert_eq!(
            got,
            vec![
                "SKU1:blue:5",
                "SKU4:red:2",
                "SKU8:blue:7",
            ]
        );
    }

    #[test]
    fn ignores_bad_records_without_panicking() {
        let input = [
            "broken",
            "sku9|active|x|blue",
            "sku10|active|4|clearance",
            "sku11|active|1| green ",
        ];

        let got = collect_active_codes(&input);
        assert_eq!(got, vec!["SKU11:green:1"]);
    }
}
