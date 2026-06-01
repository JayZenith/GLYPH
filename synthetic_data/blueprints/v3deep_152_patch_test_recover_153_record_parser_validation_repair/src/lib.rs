pub fn parse_record(line: &str) -> Result<(&str, u16, bool), String> {
    let parts: Vec<&str> = line.split(';').collect();
    if parts.len() != 3 {
        return Err("expected 3 fields".to_string());
    }

    let name = parts[0];
    if name.is_empty() {
        return Err("name missing".to_string());
    }

    let count: u16 = parts[1].parse().map_err(|_| "invalid count".to_string())?;

    let enabled = match parts[2] {
        "yes" => true,
        "no" => false,
        _ => return Err("invalid enabled flag".to_string()),
    };

    Ok((name, count, enabled))
}

#[cfg(test)]
mod tests {
    use super::parse_record;

    #[test]
    fn parses_valid_record() {
        assert_eq!(parse_record("alpha;12;yes").unwrap(), ("alpha", 12, true));
    }

    #[test]
    fn trims_fields_before_parsing() {
        assert_eq!(parse_record("  beta ; 7 ; no ").unwrap(), ("beta", 7, false));
    }

    #[test]
    fn rejects_count_with_leading_zeroes() {
        assert!(parse_record("gamma;007;yes").is_err());
        assert_eq!(parse_record("gamma;0;yes").unwrap(), ("gamma", 0, true));
    }

    #[test]
    fn accepts_case_insensitive_flag() {
        assert_eq!(parse_record("delta;3;YES").unwrap(), ("delta", 3, true));
        assert_eq!(parse_record("delta;3;No").unwrap(), ("delta", 3, false));
    }

    #[test]
    fn rejects_extra_delimiters_even_if_trailing_empty() {
        assert!(parse_record("omega;5;yes;").is_err());
    }
}
