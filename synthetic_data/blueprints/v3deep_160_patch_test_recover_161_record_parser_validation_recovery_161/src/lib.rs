pub fn parse_records(input: &str) -> Result<Vec<(String, u32, bool)>, String> {
    let mut out = Vec::new();
    for line in input.lines() {
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 3 {
            return Err(format!("bad record: {}", line));
        }

        let name = parts[0].to_string();
        let qty = parts[1].parse::<u32>().unwrap_or(0);
        let active = parts[2] == "true";
        out.push((name, qty, active));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::parse_records;

    #[test]
    fn parses_valid_lines_and_skips_comments() {
        let input = "# inventory\napple|12|true\n\npear|0|false\n";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                ("apple".to_string(), 12, true),
                ("pear".to_string(), 0, false),
            ]
        );
    }

    #[test]
    fn trims_fields_and_accepts_yes_no_flags() {
        let input = "  kiwi | 7 | yes \nmelon| 3 | no\n";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                ("kiwi".to_string(), 7, true),
                ("melon".to_string(), 3, false),
            ]
        );
    }

    #[test]
    fn rejects_extra_columns() {
        let err = parse_records("apple|1|true|extra\n").unwrap_err();
        assert!(err.contains("bad record"));
    }

    #[test]
    fn rejects_invalid_quantity() {
        let err = parse_records("apple|xyz|true\n").unwrap_err();
        assert!(err.contains("bad qty"));
    }

    #[test]
    fn rejects_invalid_flag() {
        let err = parse_records("apple|4|maybe\n").unwrap_err();
        assert!(err.contains("bad active"));
    }

    #[test]
    fn rejects_empty_name() {
        let err = parse_records("   |4|true\n").unwrap_err();
        assert!(err.contains("bad name"));
    }
}
