#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub tag: String,
    pub value: i32,
    pub note: Option<String>,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (idx, raw) in input.lines().enumerate() {
        let line_no = idx + 1;
        if raw.trim().is_empty() {
            continue;
        }

        let mut id = 0u32;
        let mut tag = String::new();
        let mut value = 0i32;
        let mut note = None;

        for part in raw.split('|') {
            let mut kv = part.splitn(2, '=');
            let key = kv.next().unwrap_or("");
            let val = kv.next().unwrap_or("");
            match key {
                "id" => {
                    id = val.parse().map_err(|_| format!("line {}: bad id", line_no))?;
                }
                "tag" => {
                    tag = val.to_string();
                }
                "value" => {
                    value = val.parse().map_err(|_| format!("line {}: bad value", line_no))?;
                }
                "note" => {
                    note = Some(val.to_string());
                }
                _ => {}
            }
        }

        if id == 0 {
            return Err(format!("line {}: missing id", line_no));
        }
        if tag.is_empty() {
            return Err(format!("line {}: missing tag", line_no));
        }

        out.push(Record { id, tag, value, note });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records_and_optional_note() {
        let input = "id=1|tag=alpha|value=10\nid=2|tag=beta-9|value=-3|note=keep";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    id: 1,
                    tag: "alpha".to_string(),
                    value: 10,
                    note: None,
                },
                Record {
                    id: 2,
                    tag: "beta-9".to_string(),
                    value: -3,
                    note: Some("keep".to_string()),
                }
            ]
        );
    }

    #[test]
    fn rejects_missing_required_value_field() {
        let err = parse_records("id=1|tag=alpha").unwrap_err();
        assert_eq!(err, "line 1: missing value");
    }

    #[test]
    fn rejects_unknown_field_name() {
        let err = parse_records("id=1|tag=alpha|value=4|extra=nope").unwrap_err();
        assert_eq!(err, "line 1: unknown field extra");
    }

    #[test]
    fn rejects_duplicate_field_name() {
        let err = parse_records("id=1|tag=alpha|value=4|tag=beta").unwrap_err();
        assert_eq!(err, "line 1: duplicate field tag");
    }

    #[test]
    fn rejects_malformed_segment_without_equals() {
        let err = parse_records("id=1|tag=alpha|value=4|broken").unwrap_err();
        assert_eq!(err, "line 1: malformed segment broken");
    }

    #[test]
    fn rejects_invalid_tag_shape() {
        let err = parse_records("id=1|tag=Bad_Tag|value=4").unwrap_err();
        assert_eq!(err, "line 1: invalid tag");
    }

    #[test]
    fn rejects_value_out_of_range() {
        let err = parse_records("id=1|tag=alpha|value=1001").unwrap_err();
        assert_eq!(err, "line 1: value out of range");
    }

    #[test]
    fn note_cannot_be_empty_when_present() {
        let err = parse_records("id=1|tag=alpha|value=4|note=").unwrap_err();
        assert_eq!(err, "line 1: empty note");
    }

    #[test]
    fn reports_first_bad_line_number() {
        let input = "id=1|tag=alpha|value=4\nid=2|tag=beta|value=7|extra=bad\nid=3|tag=gamma|value=9";
        let err = parse_records(input).unwrap_err();
        assert_eq!(err, "line 2: unknown field extra");
    }
}
