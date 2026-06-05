#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventRecord {
    pub id: String,
    pub kind: String,
    pub value: u32,
    pub tags: Vec<String>,
}

pub fn parse_records(input: &str) -> Result<Vec<EventRecord>, String> {
    let mut out = Vec::new();
    for (idx, raw) in input.lines().enumerate() {
        let line_no = idx + 1;
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut id = String::new();
        let mut kind = String::new();
        let mut value = 0u32;
        let mut tags = Vec::new();

        for part in line.split(';') {
            let mut kv = part.splitn(2, '=');
            let key = kv.next().unwrap_or("").trim();
            let val = kv.next().unwrap_or("").trim();
            match key {
                "id" => id = val.to_string(),
                "kind" => kind = val.to_string(),
                "value" => {
                    value = val.parse::<u32>().map_err(|_| format!("line {}: bad value", line_no))?;
                }
                "tags" => {
                    tags = val
                        .split(',')
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty())
                        .collect();
                }
                _ => {}
            }
        }

        if id.is_empty() {
            return Err(format!("line {}: missing id", line_no));
        }
        if kind.is_empty() {
            kind = "generic".to_string();
        }

        out.push(EventRecord { id, kind, value, tags });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "id=abc123;kind=metric;value=42;tags=red,blue\nid=z9;kind=event;value=0;tags=solo";
        let got = parse_records(input).unwrap();
        assert_eq!(got.len(), 2);
        assert_eq!(got[0].id, "abc123");
        assert_eq!(got[0].kind, "metric");
        assert_eq!(got[0].value, 42);
        assert_eq!(got[0].tags, vec!["red", "blue"]);
        assert_eq!(got[1].id, "z9");
        assert_eq!(got[1].tags, vec!["solo"]);
    }

    #[test]
    fn rejects_missing_required_fields() {
        let err = parse_records("kind=metric;value=5;tags=x").unwrap_err();
        assert_eq!(err, "line 1: missing id");

        let err = parse_records("id=abc123;value=5;tags=x").unwrap_err();
        assert_eq!(err, "line 1: missing kind");

        let err = parse_records("id=abc123;kind=metric;tags=x").unwrap_err();
        assert_eq!(err, "line 1: missing value");
    }

    #[test]
    fn rejects_malformed_or_unknown_fields() {
        let err = parse_records("id=abc123;kind=metric;oops;value=5;tags=x").unwrap_err();
        assert_eq!(err, "line 1: malformed field 'oops'");

        let err = parse_records("id=abc123;kind=metric;value=5;extra=nope;tags=x").unwrap_err();
        assert_eq!(err, "line 1: unknown field 'extra'");
    }

    #[test]
    fn validates_id_kind_and_tags() {
        let err = parse_records("id=bad-id;kind=metric;value=5;tags=x").unwrap_err();
        assert_eq!(err, "line 1: invalid id");

        let err = parse_records("id=abc123;kind=Metric;value=5;tags=x").unwrap_err();
        assert_eq!(err, "line 1: invalid kind");

        let err = parse_records("id=abc123;kind=metric;value=5;tags=").unwrap_err();
        assert_eq!(err, "line 1: missing tags");

        let err = parse_records("id=abc123;kind=metric;value=5;tags=ok,bad-tag").unwrap_err();
        assert_eq!(err, "line 1: invalid tag 'bad-tag'");
    }

    #[test]
    fn validates_value_range_and_duplicates() {
        let err = parse_records("id=abc123;kind=metric;value=1001;tags=x").unwrap_err();
        assert_eq!(err, "line 1: value out of range");

        let err = parse_records("id=abc123;kind=metric;value=5;tags=x;id=zzz999").unwrap_err();
        assert_eq!(err, "line 1: duplicate field 'id'");
    }
}
