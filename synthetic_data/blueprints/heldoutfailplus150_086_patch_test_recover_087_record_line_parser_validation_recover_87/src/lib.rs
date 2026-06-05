#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub kind: String,
    pub value: i32,
    pub tags: Vec<String>,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut id = None;
    let mut kind = None;
    let mut value = None;
    let mut tags: Vec<String> = Vec::new();

    for part in line.split('|') {
        let Some((key, raw_val)) = part.split_once('=') else {
            continue;
        };
        let key = key.trim();
        let raw_val = raw_val.trim();
        match key {
            "id" => {
                id = raw_val.parse::<u32>().ok();
            }
            "kind" => {
                kind = Some(raw_val.to_string());
            }
            "value" => {
                value = raw_val.parse::<i32>().ok();
            }
            "tags" => {
                tags = raw_val
                    .split(',')
                    .filter(|s| !s.is_empty())
                    .map(|s| s.to_string())
                    .collect();
            }
            _ => {}
        }
    }

    let id = id.ok_or_else(|| "missing id".to_string())?;
    let kind = kind.ok_or_else(|| "missing kind".to_string())?;
    let value = value.unwrap_or(0);

    Ok(Record { id, kind, value, tags })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_alert_record() {
        let rec = parse_record("id=7|kind=alert|value=3|tags=urgent,ops").unwrap();
        assert_eq!(rec.id, 7);
        assert_eq!(rec.kind, "alert");
        assert_eq!(rec.value, 3);
        assert_eq!(rec.tags, vec!["urgent", "ops"]);
    }

    #[test]
    fn requires_well_formed_segments() {
        assert_eq!(parse_record("id=3|kind=metric|value=8|broken").unwrap_err(), "malformed segment");
    }

    #[test]
    fn requires_all_required_fields() {
        assert_eq!(parse_record("id=3|value=8|tags=ops").unwrap_err(), "missing kind");
        assert_eq!(parse_record("kind=metric|value=8|tags=ops").unwrap_err(), "missing id");
        assert_eq!(parse_record("id=3|kind=metric|tags=ops").unwrap_err(), "missing value");
    }

    #[test]
    fn rejects_unknown_and_duplicate_fields() {
        assert_eq!(parse_record("id=3|kind=metric|value=8|extra=x").unwrap_err(), "unknown field: extra");
        assert_eq!(parse_record("id=3|kind=metric|value=8|id=4").unwrap_err(), "duplicate field: id");
    }

    #[test]
    fn validates_kind_and_value_ranges() {
        assert_eq!(parse_record("id=3|kind=other|value=8").unwrap_err(), "invalid kind");
        assert_eq!(parse_record("id=3|kind=metric|value=-1").unwrap_err(), "metric value out of range");
        assert_eq!(parse_record("id=3|kind=metric|value=101").unwrap_err(), "metric value out of range");
        assert_eq!(parse_record("id=3|kind=alert|value=0").unwrap_err(), "alert value out of range");
        assert_eq!(parse_record("id=3|kind=alert|value=11").unwrap_err(), "alert value out of range");
    }

    #[test]
    fn validates_tags_by_kind() {
        assert_eq!(parse_record("id=3|kind=alert|value=5").unwrap_err(), "missing tags");
        assert_eq!(parse_record("id=3|kind=alert|value=5|tags=urgent,bad-tag").unwrap_err(), "invalid tag");
        assert_eq!(parse_record("id=3|kind=alert|value=5|tags=urgent,urgent").unwrap_err(), "duplicate tag");
        let rec = parse_record("id=3|kind=metric|value=5|tags=").unwrap();
        assert!(rec.tags.is_empty());
        assert_eq!(parse_record("id=3|kind=metric|value=5|tags=ops").unwrap_err(), "metric tags must be empty");
    }
}
