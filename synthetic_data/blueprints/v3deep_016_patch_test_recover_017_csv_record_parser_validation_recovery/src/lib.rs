#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub name: String,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for (idx, raw_line) in input.lines().enumerate() {
        if raw_line.is_empty() {
            continue;
        }

        let parts: Vec<&str> = raw_line.split(',').collect();
        if parts.len() < 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let id = parts[0].parse::<u32>().map_err(|_| format!("line {}: invalid id", idx + 1))?;
        let name = parts[1].to_string();
        let active = parts[2] == "true";

        out.push(Record { id, name, active });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_rows_with_spaces() {
        let input = "1, Alice , true\n2,Bob,false";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    id: 1,
                    name: "Alice".into(),
                    active: true,
                },
                Record {
                    id: 2,
                    name: "Bob".into(),
                    active: false,
                },
            ]
        );
    }

    #[test]
    fn rejects_lines_with_extra_fields() {
        let err = parse_records("1,Alice,true,extra").unwrap_err();
        assert_eq!(err, "line 1: expected 3 fields");
    }

    #[test]
    fn rejects_invalid_boolean_text() {
        let err = parse_records("1,Alice,yes").unwrap_err();
        assert_eq!(err, "line 1: invalid active");
    }

    #[test]
    fn rejects_blank_name_after_trim() {
        let err = parse_records("1,   ,true").unwrap_err();
        assert_eq!(err, "line 1: empty name");
    }

    #[test]
    fn skips_whitespace_only_lines() {
        let got = parse_records("  \n1,Alice,true\n\t\n2,Bob,false").unwrap();
        assert_eq!(got.len(), 2);
    }
}
