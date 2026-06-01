#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub age: u8,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (idx, line) in input.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        let parts: Vec<_> = line.split('|').collect();
        if parts.len() != 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let name = parts[0].to_string();
        if name.is_empty() {
            return Err(format!("line {}: empty name", idx + 1));
        }

        let age: u8 = parts[1].parse().map_err(|_| format!("line {}: invalid age", idx + 1))?;

        let active = match parts[2] {
            "true" => true,
            "false" => false,
            _ => return Err(format!("line {}: invalid active flag", idx + 1)),
        };

        out.push(Record { name, age, active });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_input_and_ignores_blank_lines() {
        let input = " Alice | 30 | true \n\nBob|7|false\n";
        let records = parse_records(input).unwrap();
        assert_eq!(
            records,
            vec![
                Record {
                    name: "Alice".into(),
                    age: 30,
                    active: true,
                },
                Record {
                    name: "Bob".into(),
                    age: 7,
                    active: false,
                }
            ]
        );
    }

    #[test]
    fn rejects_non_ascii_names() {
        let err = parse_records("Zoë|22|true").unwrap_err();
        assert_eq!(err, "line 1: invalid name");
    }

    #[test]
    fn rejects_names_with_digits() {
        let err = parse_records("Al1ce|22|true").unwrap_err();
        assert_eq!(err, "line 1: invalid name");
    }

    #[test]
    fn rejects_age_out_of_range() {
        let err = parse_records("Alice|130|true").unwrap_err();
        assert_eq!(err, "line 1: age out of range");
    }

    #[test]
    fn accepts_yes_no_flags_case_insensitively() {
        let records = parse_records("Alice|30|YES\nBob|40|no").unwrap();
        assert_eq!(records[0].active, true);
        assert_eq!(records[1].active, false);
    }

    #[test]
    fn reports_wrong_field_count() {
        let err = parse_records("Alice|30").unwrap_err();
        assert_eq!(err, "line 1: expected 3 fields");
    }
}
