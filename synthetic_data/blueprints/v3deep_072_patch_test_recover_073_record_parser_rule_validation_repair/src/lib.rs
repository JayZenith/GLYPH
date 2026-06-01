#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub age: u8,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut name: Option<String> = None;
    let mut age: Option<u8> = None;
    let mut active: Option<bool> = None;

    for field in line.split('|') {
        if field.is_empty() {
            continue;
        }

        let mut parts = field.splitn(2, '=');
        let key = parts.next().unwrap_or("");
        let value = parts.next().unwrap_or("");

        match key {
            "name" => name = Some(value.to_string()),
            "age" => age = value.parse::<u8>().ok(),
            "active" => active = Some(value == "true" || value == "yes" || value == "1"),
            _ => {}
        }
    }

    Ok(Record {
        name: name.unwrap_or_default(),
        age: age.unwrap_or(0),
        active: active.unwrap_or(false),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let rec = parse_record("name=Alice|age=34|active=yes").unwrap();
        assert_eq!(rec, Record { name: "Alice".into(), age: 34, active: true });
    }

    #[test]
    fn requires_all_fields() {
        assert!(parse_record("name=Alice|active=true").is_err());
        assert!(parse_record("age=34|active=true").is_err());
    }

    #[test]
    fn rejects_unknown_keys() {
        assert!(parse_record("name=Alice|age=34|active=true|role=admin").is_err());
    }

    #[test]
    fn rejects_bad_boolean_values() {
        assert!(parse_record("name=Alice|age=34|active=maybe").is_err());
    }

    #[test]
    fn rejects_empty_name_and_out_of_range_age() {
        assert!(parse_record("name=|age=34|active=true").is_err());
        assert!(parse_record("name=Alice|age=130|active=true").is_err());
    }

    #[test]
    fn rejects_malformed_fields() {
        assert!(parse_record("name=Alice|age|active=true").is_err());
        assert!(parse_record("name=Alice||age=34|active=true").is_err());
    }
}
