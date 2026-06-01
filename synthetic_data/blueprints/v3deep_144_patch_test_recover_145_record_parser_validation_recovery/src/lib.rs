pub fn parse_records(input: &str) -> Result<Vec<(String, u32, bool)>, String> {
    let mut out = Vec::new();
    for (idx, line) in input.lines().enumerate() {
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() != 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let name = parts[0].to_string();
        if name.is_empty() {
            return Err(format!("line {}: empty name", idx + 1));
        }

        let qty = parts[1].parse::<u32>().map_err(|_| format!("line {}: invalid qty", idx + 1))?;

        let active = match parts[2] {
            "true" => true,
            "false" => false,
            _ => return Err(format!("line {}: invalid active", idx + 1)),
        };

        out.push((name, qty, active));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::parse_records;

    #[test]
    fn parses_valid_rows_with_trimming_and_blank_lines() {
        let input = "  apple | 3 | true\n\nbanana|10|false\n";
        let rows = parse_records(input).unwrap();
        assert_eq!(rows, vec![
            ("apple".to_string(), 3, true),
            ("banana".to_string(), 10, false),
        ]);
    }

    #[test]
    fn rejects_bad_field_count() {
        let err = parse_records("pear|7").unwrap_err();
        assert_eq!(err, "line 1: expected 3 fields");
    }

    #[test]
    fn rejects_name_with_non_letters() {
        let err = parse_records("appl3|7|true").unwrap_err();
        assert_eq!(err, "line 1: invalid name");
    }

    #[test]
    fn rejects_qty_with_leading_zeroes() {
        let err = parse_records("pear|007|true").unwrap_err();
        assert_eq!(err, "line 1: invalid qty");
    }

    #[test]
    fn accepts_yes_no_for_active() {
        let rows = parse_records("pear|7|yes\nplum|2|no").unwrap();
        assert_eq!(rows, vec![
            ("pear".to_string(), 7, true),
            ("plum".to_string(), 2, false),
        ]);
    }
}
