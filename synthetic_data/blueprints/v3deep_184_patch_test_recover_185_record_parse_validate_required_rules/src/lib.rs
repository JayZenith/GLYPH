#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub name: String,
    pub active: bool,
    pub tags: Vec<String>,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut id = 0;
    let mut name = String::new();
    let mut active = false;
    let mut tags = Vec::new();

    for part in line.split(';') {
        let mut kv = part.splitn(2, '=');
        let key = kv.next().unwrap_or("");
        let value = kv.next().unwrap_or("");
        match key {
            "id" => id = value.parse().unwrap_or(0),
            "name" => name = value.to_string(),
            "active" => active = value == "true",
            "tags" => {
                tags = value.split(',').map(|s| s.to_string()).collect();
            }
            _ => {}
        }
    }

    Ok(Record { id, name, active, tags })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let rec = parse_record("id=7;name=Alice;active=true;tags=red,blue").unwrap();
        assert_eq!(rec.id, 7);
        assert_eq!(rec.name, "Alice");
        assert!(rec.active);
        assert_eq!(rec.tags, vec!["red", "blue"]);
    }

    #[test]
    fn trims_around_keys_and_values() {
        let rec = parse_record(" id = 9 ; name = Bob ; active = false ; tags = one, two , three ").unwrap();
        assert_eq!(rec.id, 9);
        assert_eq!(rec.name, "Bob");
        assert!(!rec.active);
        assert_eq!(rec.tags, vec!["one", "two", "three"]);
    }

    #[test]
    fn rejects_missing_required_fields() {
        assert!(parse_record("name=NoId;active=true;tags=x").is_err());
        assert!(parse_record("id=3;active=true;tags=x").is_err());
    }

    #[test]
    fn rejects_invalid_id_and_active_values() {
        assert!(parse_record("id=abc;name=Bad;active=true;tags=x").is_err());
        assert!(parse_record("id=4;name=Bad;active=yes;tags=x").is_err());
    }

    #[test]
    fn rejects_empty_tag_entries_and_duplicate_keys() {
        assert!(parse_record("id=1;name=A;active=true;tags=ok,,bad").is_err());
        assert!(parse_record("id=1;name=A;name=B;active=true;tags=ok").is_err());
    }
}
