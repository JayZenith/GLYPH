pub fn collect_alert_codes(lines: &[&str]) -> Vec<String> {
    lines
        .iter()
        .filter_map(|line| {
            let trimmed = line.trim();
            let (level, rest) = trimmed.split_once(':')?;
            if level != "WARN" && level != "ERROR" {
                return None;
            }

            let code = rest.split_whitespace().next()?;
            if !code.starts_with("A-") {
                return None;
            }
            if code.len() < 4 {
                return None;
            }

            Some(code.to_string())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_alert_codes;

    #[test]
    fn keeps_warn_and_error_codes_with_dedup_and_uppercase() {
        let lines = [
            "INFO: A-100 ignored",
            "WARN: A-100 low battery",
            "warn: a-101 lowercase still valid",
            "ERROR: A-100 duplicate from error",
            "ERROR: B-200 wrong prefix",
            "ERROR: A-9 too short",
            "ERROR A-777 malformed",
            "  ERROR: a-305 sensor offline  ",
        ];

        assert_eq!(
            collect_alert_codes(&lines),
            vec!["A-100", "A-101", "A-305"]
        );
    }

    #[test]
    fn ignores_blank_codes_and_strips_trailing_punctuation() {
        let lines = [
            "WARN: A-210, disk almost full",
            "ERROR: A-211; network unstable",
            "WARN: A-212! noisy fan",
            "ERROR: A-213? thermal spike",
            "WARN: A-214. note",
            "ERROR: A-   missing digits",
            "WARN:    ",
        ];

        assert_eq!(
            collect_alert_codes(&lines),
            vec!["A-210", "A-211", "A-212", "A-213", "A-214"]
        );
    }

    #[test]
    fn keeps_input_order_after_filtering() {
        let lines = [
            "ERROR: a-401 first",
            "INFO: A-999 skipped",
            "WARN: A-205 second",
            "DEBUG: A-000 skipped",
            "ERROR: A-330 third",
        ];

        assert_eq!(
            collect_alert_codes(&lines),
            vec!["A-401", "A-205", "A-330"]
        );
    }
}
