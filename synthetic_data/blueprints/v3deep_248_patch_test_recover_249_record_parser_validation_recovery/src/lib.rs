#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub active: bool,
    pub tags: Vec<String>,
}

pub fn parse_record(input: &str) -> Result<Record, String> {
    let mut id = None;
    let mut active = None;
    let mut tags: Vec<String> = Vec::new();

    for part in input.split(';') {
        if let Some((key, value)) = part.split_once('=') {
            let key = key.trim();
            let value = value.trim();
            match key {
                "id" => {
                    id = value.parse::<u32>().ok();
                }
                "active" => {
                    active = Some(value == "true");
                }
                "tags" => {
                    if !value.is_empty() {
                        tags = value.split(',').map(|s| s.to_string()).collect();
                    }
                }
                _ => {}
            }
        }
    }

    Ok(Record {
        id: id.unwrap_or(0),
        active: active.unwrap_or(false),
        tags,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let r = parse_record("id=42;active=true;tags=red,blue").unwrap();
        assert_eq!(
            r,
            Record {
                id: 42,
                active: true,
                tags: vec!["red".into(), "blue".into()]
            }
        );
    }

    #[test]
    fn trims_tag_items() {
        let r = parse_record("id=7;active=false;tags= alpha , beta ").unwrap();
        assert_eq!(r.tags, vec!["alpha", "beta"]);
    }

    #[test]
    fn rejects_missing_required_id() {
        assert_eq!(parse_record("active=true;tags=x"), Err("missing id".into()));
    }

    #[test]
    fn rejects_invalid_active_value() {
        assert_eq!(
            parse_record("id=5;active=yes;tags=x"),
            Err("invalid active".into())
        );
    }

    #[test]
    fn rejects_empty_tag_and_duplicate_tags() {
        assert_eq!(
            parse_record("id=3;active=true;tags=red,,blue"),
            Err("invalid tags".into())
        );
        assert_eq!(
            parse_record("id=3;active=true;tags=red,blue,red"),
            Err("duplicate tag".into())
        );
    }

    #[test]
    fn rejects_unknown_field() {
        assert_eq!(
            parse_record("id=1;active=true;mode=fast"),
            Err("unknown field".into())
        );
    }
}
