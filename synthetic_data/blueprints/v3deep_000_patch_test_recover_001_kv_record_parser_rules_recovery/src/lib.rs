#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub age: u8,
    pub active: bool,
}

pub fn parse_record(input: &str) -> Result<Record, String> {
    let mut name = None;
    let mut age = None;
    let mut active = None;

    for part in input.split(';') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }

        let (key, value) = part
            .split_once(':')
            .ok_or_else(|| format!("invalid field: {part}"))?;

        match key {
            "name" => name = Some(value.to_string()),
            "age" => age = value.parse::<u8>().ok(),
            "active" => active = Some(value == "true"),
            _ => {}
        }
    }

    match (name, age, active) {
        (Some(name), Some(age), Some(active)) => Ok(Record { name, age, active }),
        _ => Err("missing field".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let rec = parse_record("name: Alice ; age: 34 ; active: true").unwrap();
        assert_eq!(
            rec,
            Record {
                name: "Alice".to_string(),
                age: 34,
                active: true,
            }
        );
    }

    #[test]
    fn rejects_unknown_keys() {
        assert_eq!(
            parse_record("name:Bob;age:20;active:true;role:admin"),
            Err("unknown field: role".to_string())
        );
    }

    #[test]
    fn rejects_duplicate_keys() {
        assert_eq!(
            parse_record("name:Bob;name:Rob;age:20;active:true"),
            Err("duplicate field: name".to_string())
        );
    }

    #[test]
    fn trims_and_validates_boolean() {
        assert_eq!(
            parse_record("name:Bob;age:20;active: yes"),
            Err("invalid active: yes".to_string())
        );
    }

    #[test]
    fn validates_age_range() {
        assert_eq!(
            parse_record("name:Bob;age:0;active:false"),
            Err("age out of range: 0".to_string())
        );
    }
}
