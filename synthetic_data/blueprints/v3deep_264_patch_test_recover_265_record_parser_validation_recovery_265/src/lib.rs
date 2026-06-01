pub fn parse_records(input: &str) -> Result<Vec<(String, u16, bool)>, String> {
    let mut out = Vec::new();

    for (idx, raw_line) in input.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() != 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let name = parts[0].to_string();

        let qty = parts[1]
            .parse::<u16>()
            .map_err(|_| format!("line {}: invalid quantity", idx + 1))?;

        let enabled = match parts[2] {
            "true" => true,
            "false" => false,
            _ => return Err(format!("line {}: invalid enabled flag", idx + 1)),
        };

        out.push((name, qty, enabled));
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::parse_records;

    #[test]
    fn parses_valid_input_with_comments_and_spacing() {
        let input = "\n  # inventory\n apple | 12 | true\n\n banana|0|false\n";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                ("apple".to_string(), 12, true),
                ("banana".to_string(), 0, false)
            ]
        );
    }

    #[test]
    fn rejects_empty_name() {
        let err = parse_records("  |5|true").unwrap_err();
        assert_eq!(err, "line 1: empty name");
    }

    #[test]
    fn rejects_leading_zero_quantity() {
        let err = parse_records("pear|007|false").unwrap_err();
        assert_eq!(err, "line 1: invalid quantity");
    }

    #[test]
    fn rejects_duplicate_names_case_insensitively() {
        let err = parse_records("Widget|1|true\nwidget|2|false").unwrap_err();
        assert_eq!(err, "line 2: duplicate name");
    }

    #[test]
    fn rejects_invalid_flag_after_trimming() {
        let err = parse_records("ok|2| yes ").unwrap_err();
        assert_eq!(err, "line 1: invalid enabled flag");
    }
}
