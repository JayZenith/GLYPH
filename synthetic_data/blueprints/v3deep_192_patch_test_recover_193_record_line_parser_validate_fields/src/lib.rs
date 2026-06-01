#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub kind: String,
    pub active: bool,
    pub tags: Vec<String>,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return Err("expected 4 fields".into());
    }

    let id = parts[0].parse::<u32>().map_err(|_| "invalid id".to_string())?;

    let kind = parts[1].to_string();

    let active = match parts[2] {
        "true" => true,
        "false" => false,
        _ => return Err("invalid active".into()),
    };

    let tags = if parts[3].is_empty() {
        Vec::new()
    } else {
        parts[3].split(',').map(|s| s.to_string()).collect()
    };

    Ok(Record { id, kind, active, tags })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_trimmed_fields() {
        let r = parse_record(" 42 | beta | true | red, blue ").unwrap();
        assert_eq!(
            r,
            Record {
                id: 42,
                kind: "beta".to_string(),
                active: true,
                tags: vec!["red".to_string(), "blue".to_string()],
            }
        );
    }

    #[test]
    fn rejects_wrong_field_count() {
        assert_eq!(parse_record("1|alpha|true").unwrap_err(), "expected 4 fields");
        assert_eq!(parse_record("1|alpha|true|x|extra").unwrap_err(), "expected 4 fields");
    }

    #[test]
    fn rejects_unknown_kind() {
        assert_eq!(parse_record("7|gamma|false|x").unwrap_err(), "invalid kind");
    }

    #[test]
    fn rejects_empty_or_duplicate_tags() {
        assert_eq!(parse_record("5|alpha|true|one,,two").unwrap_err(), "invalid tags");
        assert_eq!(parse_record("5|alpha|true|one, two,one").unwrap_err(), "invalid tags");
    }

    #[test]
    fn empty_tags_field_is_allowed() {
        let r = parse_record("9|alpha|false|").unwrap();
        assert!(r.tags.is_empty());
    }
}
