#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() != 3 {
        return Err("expected 3 fields".to_string());
    }

    let name = parts[0].to_string();
    if name.is_empty() {
        return Err("name required".to_string());
    }

    let qty = parts[1].parse::<u32>().map_err(|_| "invalid qty".to_string())?;
    let active = parts[2] == "true";

    Ok(Record { name, qty, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_trimmed_fields() {
        let rec = parse_record("  apples  | 42 | true ").unwrap();
        assert_eq!(rec, Record {
            name: "apples".to_string(),
            qty: 42,
            active: true,
        });
    }

    #[test]
    fn rejects_empty_name_after_trimming() {
        assert_eq!(parse_record("   |5|false").unwrap_err(), "name required");
    }

    #[test]
    fn rejects_zero_quantity() {
        assert_eq!(parse_record("oranges|0|false").unwrap_err(), "qty must be positive");
    }

    #[test]
    fn rejects_non_boolean_status() {
        assert_eq!(parse_record("pears|3|yes").unwrap_err(), "invalid active");
    }

    #[test]
    fn rejects_extra_fields() {
        assert_eq!(parse_record("kiwi|2|true|extra").unwrap_err(), "expected 3 fields");
    }
}
