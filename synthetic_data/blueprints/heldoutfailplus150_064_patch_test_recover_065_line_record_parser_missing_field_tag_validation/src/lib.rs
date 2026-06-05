#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub kind: String,
    pub id: u32,
    pub value: String,
    pub tags: Vec<String>,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (idx, raw) in input.lines().enumerate() {
        let line_no = idx + 1;
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut kind = None;
        let mut id = 0u32;
        let mut value = String::new();
        let mut tags = Vec::new();

        for part in line.split('|') {
            let mut kv = part.splitn(2, '=');
            let key = kv.next().unwrap_or("").trim();
            let val = kv.next().unwrap_or("").trim();
            match key {
                "kind" => kind = Some(val.to_string()),
                "id" => id = val.parse().unwrap_or(0),
                "value" => value = val.to_string(),
                "tags" => {
                    if !val.is_empty() {
                        tags = val.split(',').map(|s| s.trim().to_string()).collect();
                    }
                }
                _ => {}
            }
        }

        if kind.is_none() {
            return Err(format!("line {} missing kind", line_no));
        }

        out.push(Record {
            kind: kind.unwrap(),
            id,
            value,
            tags,
        });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_well_formed_records() {
        let input = "kind=item|id=7|value=ok|tags=red,blue\nkind=event|id=9|value=start|tags=ops";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    kind: "item".into(),
                    id: 7,
                    value: "ok".into(),
                    tags: vec!["red".into(), "blue".into()],
                },
                Record {
                    kind: "event".into(),
                    id: 9,
                    value: "start".into(),
                    tags: vec!["ops".into()],
                },
            ]
        );
    }

    #[test]
    fn rejects_missing_required_fields() {
        let err = parse_records("kind=item|value=ok|tags=red").unwrap_err();
        assert_eq!(err, "line 1 missing id");

        let err = parse_records("kind=item|id=4|tags=red").unwrap_err();
        assert_eq!(err, "line 1 missing value");
    }

    #[test]
    fn rejects_malformed_parts_and_unknown_keys() {
        let err = parse_records("kind=item|id=4|value=ok|badpart|tags=red").unwrap_err();
        assert_eq!(err, "line 1 malformed field 'badpart'");

        let err = parse_records("kind=item|id=4|value=ok|extra=nope|tags=red").unwrap_err();
        assert_eq!(err, "line 1 unknown field 'extra'");
    }

    #[test]
    fn rejects_invalid_kind_and_id() {
        let err = parse_records("kind=other|id=4|value=ok|tags=red").unwrap_err();
        assert_eq!(err, "line 1 invalid kind 'other'");

        let err = parse_records("kind=item|id=0|value=ok|tags=red").unwrap_err();
        assert_eq!(err, "line 1 invalid id '0'");

        let err = parse_records("kind=item|id=abc|value=ok|tags=red").unwrap_err();
        assert_eq!(err, "line 1 invalid id 'abc'");
    }

    #[test]
    fn rejects_invalid_values_and_tags() {
        let err = parse_records("kind=item|id=4|value=has space|tags=red").unwrap_err();
        assert_eq!(err, "line 1 invalid value 'has space'");

        let err = parse_records("kind=item|id=4|value=ok|tags=red,Red").unwrap_err();
        assert_eq!(err, "line 1 invalid tag 'Red'");

        let err = parse_records("kind=item|id=4|value=ok|tags=red,red").unwrap_err();
        assert_eq!(err, "line 1 duplicate tag 'red'");

        let err = parse_records("kind=item|id=4|value=ok|tags=").unwrap_err();
        assert_eq!(err, "line 1 missing tags");
    }
}
