#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub qty: u32,
    pub active: bool,
    pub tag: String,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut id = 0u32;
    let mut qty = 0u32;
    let mut active = false;
    let mut tag = String::new();

    for part in line.split(';') {
        let mut pieces = part.split('=');
        let key = pieces.next().unwrap_or("");
        let value = pieces.next().unwrap_or("");

        match key {
            "id" => id = value.parse().unwrap_or(0),
            "qty" => qty = value.parse().unwrap_or(0),
            "active" => active = value == "true",
            "tag" => tag = value.to_string(),
            _ => {}
        }
    }

    if qty > 100 {
        return Err("qty out of range".into());
    }

    Ok(Record { id, qty, active, tag })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let r = parse_record("id=7;qty=10;active=true;tag=blue_1").unwrap();
        assert_eq!(r.id, 7);
        assert_eq!(r.qty, 10);
        assert!(r.active);
        assert_eq!(r.tag, "blue_1");
    }

    #[test]
    fn rejects_missing_required_field() {
        assert!(parse_record("id=7;qty=10;active=true").is_err());
    }

    #[test]
    fn rejects_unknown_key() {
        assert!(parse_record("id=7;qty=10;active=true;tag=blue_1;extra=x").is_err());
    }

    #[test]
    fn rejects_duplicate_key() {
        assert!(parse_record("id=7;qty=10;qty=11;active=true;tag=blue_1").is_err());
    }

    #[test]
    fn rejects_invalid_bool() {
        assert!(parse_record("id=7;qty=10;active=yes;tag=blue_1").is_err());
    }

    #[test]
    fn rejects_non_numeric_id() {
        assert!(parse_record("id=abc;qty=10;active=true;tag=blue_1").is_err());
    }

    #[test]
    fn rejects_qty_out_of_range() {
        assert!(parse_record("id=7;qty=101;active=true;tag=blue_1").is_err());
    }

    #[test]
    fn rejects_bad_tag_chars() {
        assert!(parse_record("id=7;qty=10;active=true;tag=blue-1").is_err());
    }

    #[test]
    fn rejects_empty_segment() {
        assert!(parse_record("id=7;;qty=10;active=true;tag=blue_1").is_err());
    }
}
