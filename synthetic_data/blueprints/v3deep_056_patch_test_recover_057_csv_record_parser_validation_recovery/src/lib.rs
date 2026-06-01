#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 3 {
        return Err("expected 3 fields".to_string());
    }

    let name = parts[0].to_string();
    if name.is_empty() {
        return Err("name required".to_string());
    }

    let qty: u32 = parts[1].parse().map_err(|_| "invalid qty".to_string())?;

    let active = match parts[2] {
        "true" => true,
        "false" => false,
        _ => return Err("invalid active".to_string()),
    };

    Ok(Record { name, qty, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_spacing() {
        let rec = parse_record(" widget | 42 | false ").unwrap();
        assert_eq!(rec, Record {
            name: "widget".to_string(),
            qty: 42,
            active: false,
        });
    }

    #[test]
    fn rejects_wrong_field_count() {
        assert_eq!(parse_record("a|1").unwrap_err(), "expected 3 fields");
        assert_eq!(parse_record("a|1|true|extra").unwrap_err(), "expected 3 fields");
    }

    #[test]
    fn rejects_blank_name_after_trim() {
        assert_eq!(parse_record("   |5|true").unwrap_err(), "name required");
    }

    #[test]
    fn rejects_zero_qty() {
        assert_eq!(parse_record("gadget|0|true").unwrap_err(), "qty must be positive");
    }

    #[test]
    fn accepts_yes_no_active_flags() {
        assert!(parse_record("gadget|7|yes").unwrap().active);
        assert!(!parse_record("gadget|7|no").unwrap().active);
    }
}
