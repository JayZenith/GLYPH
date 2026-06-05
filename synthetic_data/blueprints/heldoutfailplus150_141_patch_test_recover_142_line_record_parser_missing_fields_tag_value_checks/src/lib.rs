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
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 3 {
            return Err(format!("line {}: expected at least 3 fields", idx + 1));
        }
        let id: u32 = parts[0]
            .parse()
            .map_err(|_| format!("line {}: invalid id", idx + 1))?;
        let tag = parts[1].trim().to_string();
        let value: i32 = parts[2]
            .trim()
            .parse()
            .map_err(|_| format!("line {}: invalid value", idx + 1))?;
        let note = if parts.len() >= 4 {
            let n = parts[3].trim();
            if n.is_empty() {
                None
            } else {
                Some(n.to_string())
            }
        } else {
            None
        };
        out.push(Record { id, tag, value, note });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records_and_keeps_note_text() {
        let input = "1|ALPHA|10|ready to ship\n2|BETA|-3|  keep spaces inside  ";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    id: 1,
                    tag: "ALPHA".into(),
                    value: 10,
                    note: Some("ready to ship".into())
                },
                Record {
                    id: 2,
                    tag: "BETA".into(),
                    value: -3,
                    note: Some("keep spaces inside".into())
                }
            ]
        );
    }

    #[test]
    fn rejects_missing_and_extra_fields() {
        assert_eq!(
            parse_records("7|ALPHA").unwrap_err(),
            "line 1: expected exactly 4 fields"
        );
        assert_eq!(
            parse_records("7|ALPHA|3|ok|extra").unwrap_err(),
            "line 1: expected exactly 4 fields"
        );
    }

    #[test]
    fn rejects_bad_tags() {
        assert_eq!(
            parse_records("1|Alpha|3|ok").unwrap_err(),
            "line 1: invalid tag"
        );
        assert_eq!(
            parse_records("1|AB1|3|ok").unwrap_err(),
            "line 1: invalid tag"
        );
        assert_eq!(
            parse_records("1||3|ok").unwrap_err(),
            "line 1: invalid tag"
        );
    }

    #[test]
    fn rejects_out_of_range_values() {
        assert_eq!(
            parse_records("1|ALPHA|100|ok").unwrap_err(),
            "line 1: value out of range"
        );
        assert_eq!(
            parse_records("1|ALPHA|-100|ok").unwrap_err(),
            "line 1: value out of range"
        );
    }

    #[test]
    fn rejects_note_with_embedded_colon() {
        assert_eq!(
            parse_records("1|ALPHA|5|bad:note").unwrap_err(),
            "line 1: invalid note"
        );
    }

    #[test]
    fn reports_first_failing_line() {
        let input = "1|ALPHA|5|ok\n2|BETA|999|still bad\n3|GAMMA|1|fine";
        assert_eq!(
            parse_records(input).unwrap_err(),
            "line 2: value out of range"
        );
    }
}
