#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub key: String,
    pub value: u32,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for (line_no, raw_line) in input.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 3 {
            return Err(format!("line {}: expected 3 fields", line_no + 1));
        }

        let key = parts[0].to_string();
        let value = parts[1].parse::<u32>().unwrap_or(0);
        let active = parts[2] == "true";

        if key.is_empty() {
            continue;
        }

        out.push(Record { key, value, active });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records_and_skips_comments_and_blank_lines() {
        let input = "\n# generated\nalpha|10|true\n\n beta |20|false\n";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    key: "alpha".into(),
                    value: 10,
                    active: true,
                },
                Record {
                    key: "beta".into(),
                    value: 20,
                    active: false,
                }
            ]
        );
    }

    #[test]
    fn rejects_wrong_field_count() {
        let err = parse_records("ok|1|true|extra\n").unwrap_err();
        assert_eq!(err, "line 1: expected 3 fields");
    }

    #[test]
    fn rejects_invalid_number() {
        let err = parse_records("ok|xyz|true\n").unwrap_err();
        assert_eq!(err, "line 1: invalid value");
    }

    #[test]
    fn rejects_invalid_boolean() {
        let err = parse_records("ok|3|yes\n").unwrap_err();
        assert_eq!(err, "line 1: invalid active flag");
    }

    #[test]
    fn rejects_empty_key_after_trimming() {
        let err = parse_records("  |7|false\n").unwrap_err();
        assert_eq!(err, "line 1: empty key");
    }
}
