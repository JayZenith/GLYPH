use std::collections::BTreeMap;

pub fn sales_report(rows: &[(&str, &str, i32)]) -> String {
    let mut totals: BTreeMap<&str, i32> = BTreeMap::new();

    for (region, month, amount) in rows {
        if *amount <= 0 {
            continue;
        }
        let key = *month;
        *totals.entry(key).or_insert(0) += *amount;
        let _ = region;
    }

    let mut out = String::new();
    for (month, total) in totals {
        out.push_str(&format!("{}:{}\n", month, total));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::sales_report;

    #[test]
    fn groups_by_region_then_month_and_sorts() {
        let rows = [
            ("west", "2024-02", 5),
            ("east", "2024-01", 7),
            ("west", "2024-01", 3),
            ("east", "2024-01", 2),
            ("west", "2024-02", 4),
            ("east", "2024-02", 1),
        ];

        let report = sales_report(&rows);
        let expected = "east\n2024-01:9\n2024-02:1\nTOTAL:10\nwest\n2024-01:3\n2024-02:9\nTOTAL:12";
        assert_eq!(report, expected);
    }

    #[test]
    fn skips_non_positive_and_empty_regions() {
        let rows = [
            ("", "2024-01", 4),
            ("north", "2024-01", 0),
            ("north", "2024-01", -2),
            ("north", "2024-01", 6),
            ("north", "2024-02", 1),
        ];

        let report = sales_report(&rows);
        let expected = "north\n2024-01:6\n2024-02:1\nTOTAL:7";
        assert_eq!(report, expected);
    }

    #[test]
    fn omits_region_total_when_under_threshold() {
        let rows = [
            ("solo", "2024-03", 2),
            ("solo", "2024-03", 2),
            ("solo", "2024-04", 1),
        ];

        let report = sales_report(&rows);
        let expected = "solo\n2024-03:4\n2024-04:1";
        assert_eq!(report, expected);
    }
}
