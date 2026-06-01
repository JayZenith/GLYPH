#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub name: String,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut id = 0u32;
    let mut name = String::new();
    let mut active = false;

    for part in line.split(';') {
        if part.is_empty() {
            continue;
        }
        let (key, value) = part.split_once('=').ok_or_else(|| "invalid field".to_string())?;
        match key {
            "id" => {
                id = value.parse::<u32>().map_err(|_| "bad id".to_string())?;
            }
            "name" => {
                name = value.to_string();
            }
            "active" => {
                active = value == "true";
            }
            _ => {}
        }
    }

    Ok(Record { id, name, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_spaces() {
        let rec = parse_record(" id = 42 ; name = Ada Lovelace ; active = true ").unwrap();
        assert_eq!(rec.id, 42);
        assert_eq!(rec.name, "Ada Lovelace");
        assert!(rec.active);
    }

    #[test]
    fn rejects_missing_required_fields() {
        assert!(parse_record("name=Only Name;active=true").is_err());
        assert!(parse_record("id=7;active=false").is_err());
    }

    #[test]
    fn rejects_unknown_or_duplicate_fields() {
        assert!(parse_record("id=1;name=Ada;name=Grace;active=true").is_err());
        assert!(parse_record("id=1;name=Ada;role=admin;active=true").is_err());
    }

    #[test]
    fn validates_name_and_active_value() {
        assert!(parse_record("id=2;name=   ;active=true").is_err());
        assert!(parse_record("id=2;name=Bob;active=yes").is_err());
    }

    #[test]
    fn id_must_be_positive() {
        assert!(parse_record("id=0;name=Zero;active=false").is_err());
    }
}
