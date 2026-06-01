#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub age: u8,
    pub active: bool,
}

pub fn parse_record(input: &str) -> Result<Record, String> {
    let mut name = String::new();
    let mut age = 0u8;
    let mut active = false;

    for part in input.split(',') {
        if part.is_empty() {
            continue;
        }
        let (key, value) = part.split_once('=').ok_or_else(|| "invalid field".to_string())?;
        match key {
            "name" => name = value.to_string(),
            "age" => age = value.parse::<u8>().unwrap_or(0),
            "active" => active = value == "true" || value == "yes",
            _ => {}
        }
    }

    Ok(Record { name, age, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let r = parse_record("name=Ana;age=34;active=true").unwrap();
        assert_eq!(r, Record { name: "Ana".to_string(), age: 34, active: true });
    }

    #[test]
    fn allows_spaces_around_keys_and_values() {
        let r = parse_record(" name = Bob ; age = 7 ; active = false ").unwrap();
        assert_eq!(r, Record { name: "Bob".to_string(), age: 7, active: false });
    }

    #[test]
    fn rejects_missing_required_name() {
        assert_eq!(parse_record("age=9;active=true").unwrap_err(), "missing name");
    }

    #[test]
    fn rejects_invalid_age() {
        assert_eq!(parse_record("name=Ana;age=999;active=true").unwrap_err(), "invalid age");
        assert_eq!(parse_record("name=Ana;age=nope;active=true").unwrap_err(), "invalid age");
    }

    #[test]
    fn rejects_invalid_active() {
        assert_eq!(parse_record("name=Ana;age=5;active=maybe").unwrap_err(), "invalid active");
    }

    #[test]
    fn rejects_unknown_and_malformed_fields() {
        assert_eq!(parse_record("name=Ana;age=5;role=admin;active=true").unwrap_err(), "unknown field");
        assert_eq!(parse_record("name=Ana;age;active=true").unwrap_err(), "invalid field");
    }
}
