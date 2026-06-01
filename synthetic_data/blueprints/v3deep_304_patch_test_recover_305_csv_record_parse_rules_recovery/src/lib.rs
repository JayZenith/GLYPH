#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for (idx, raw_line) in input.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let name = parts[0].to_string();
        let qty = parts[1].parse::<u32>().map_err(|_| format!("line {}: bad qty", idx + 1))?;
        let active = parts[2] == "true";

        out.push(Record { name, qty, active });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_rows_with_comments_and_spacing() {
        let input = "\n  apple | 10 | true\n# skip this\npear|2|false\n\n";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record { name: "apple".into(), qty: 10, active: true },
                Record { name: "pear".into(), qty: 2, active: false },
            ]
        );
    }

    #[test]
    fn rejects_extra_or_missing_fields() {
        assert_eq!(
            parse_records("apple|1").unwrap_err(),
            "line 1: expected 3 fields exactly"
        );
        assert_eq!(
            parse_records("apple|1|true|extra").unwrap_err(),
            "line 1: expected 3 fields exactly"
        );
    }

    #[test]
    fn rejects_blank_name_and_zero_qty() {
        assert_eq!(
            parse_records("   | 5 | true").unwrap_err(),
            "line 1: name must not be blank"
        );
        assert_eq!(
            parse_records("apple|0|true").unwrap_err(),
            "line 1: qty must be positive"
        );
    }

    #[test]
    fn accepts_yes_no_flags_and_rejects_other_values() {
        let got = parse_records("apple|3|yes\npear|4|no").unwrap();
        assert_eq!(got[0].active, true);
        assert_eq!(got[1].active, false);

        assert_eq!(
            parse_records("apple|3|maybe").unwrap_err(),
            "line 1: active must be yes or no"
        );
    }
}
