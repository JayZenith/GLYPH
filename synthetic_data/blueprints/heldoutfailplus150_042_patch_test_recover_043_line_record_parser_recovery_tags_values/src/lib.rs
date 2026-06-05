#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub key: String,
    pub value: u32,
    pub tag: String,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for (idx, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut key = "";
        let mut value = 0u32;
        let mut tag = "";

        for part in line.split('|') {
            let mut kv = part.splitn(2, '=');
            let name = kv.next().unwrap_or("").trim();
            let data = kv.next().unwrap_or("").trim();
            match name {
                "key" => key = data,
                "value" => value = data.parse::<u32>().unwrap_or(0),
                "tag" => tag = data,
                _ => {}
            }
        }

        if key.is_empty() {
            return Err(format!("line {}: missing key", idx + 1));
        }

        out.push(Record {
            key: key.to_string(),
            value,
            tag: tag.to_string(),
        });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_multiple_valid_records() {
        let input = "key=alpha|value=12|tag=core\nkey=beta_2|value=7|tag=edge";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    key: "alpha".into(),
                    value: 12,
                    tag: "core".into()
                },
                Record {
                    key: "beta_2".into(),
                    value: 7,
                    tag: "edge".into()
                }
            ]
        );
    }

    #[test]
    fn rejects_missing_required_fields() {
        let err = parse_records("key=alpha|tag=core").unwrap_err();
        assert_eq!(err, "line 1: missing value");

        let err = parse_records("value=3|tag=core").unwrap_err();
        assert_eq!(err, "line 1: missing key");

        let err = parse_records("key=alpha|value=3").unwrap_err();
        assert_eq!(err, "line 1: missing tag");
    }

    #[test]
    fn rejects_bad_field_layout_and_unknown_names() {
        let err = parse_records("key=alpha|value=3|extra=x|tag=core").unwrap_err();
        assert_eq!(err, "line 1: unknown field 'extra'");

        let err = parse_records("key=alpha|value|tag=core").unwrap_err();
        assert_eq!(err, "line 1: malformed field 'value'");

        let err = parse_records("key=alpha|value=3|tag=core|").unwrap_err();
        assert_eq!(err, "line 1: malformed field ''");
    }

    #[test]
    fn rejects_duplicate_or_out_of_order_fields() {
        let err = parse_records("key=alpha|value=3|tag=core|tag=edge").unwrap_err();
        assert_eq!(err, "line 1: duplicate field 'tag'");

        let err = parse_records("value=3|key=alpha|tag=core").unwrap_err();
        assert_eq!(err, "line 1: fields out of order");
    }

    #[test]
    fn validates_key_tag_and_value_content() {
        let err = parse_records("key=bad-key|value=3|tag=core").unwrap_err();
        assert_eq!(err, "line 1: invalid key 'bad-key'");

        let err = parse_records("key=alpha|value=0|tag=core").unwrap_err();
        assert_eq!(err, "line 1: invalid value '0'");

        let err = parse_records("key=alpha|value=abc|tag=core").unwrap_err();
        assert_eq!(err, "line 1: invalid value 'abc'");

        let err = parse_records("key=alpha|value=3|tag=misc").unwrap_err();
        assert_eq!(err, "line 1: invalid tag 'misc'");
    }

    #[test]
    fn reports_first_failing_line() {
        let input = "key=alpha|value=2|tag=core\nkey=beta|value=0|tag=edge\nkey=gamma|value=4|tag=core";
        let err = parse_records(input).unwrap_err();
        assert_eq!(err, "line 2: invalid value '0'");
    }
}
