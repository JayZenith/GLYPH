#[derive(Debug, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub age: u8,
    pub active: bool,
    pub tags: Vec<String>,
}

pub fn parse_entries(input: &str) -> Result<Vec<Entry>, String> {
    let mut out = Vec::new();
    for (line_idx, raw_line) in input.lines().enumerate() {
        let line_no = line_idx + 1;
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 4 {
            return Err(format!("line {}: expected 4 fields", line_no));
        }

        let name = parts[0].to_string();

        let age: u8 = parts[1]
            .parse()
            .map_err(|_| format!("line {}: invalid age", line_no))?;

        let active = match parts[2] {
            "true" => true,
            "false" => false,
            _ => return Err(format!("line {}: invalid active flag", line_no)),
        };

        let tags: Vec<String> = if parts[3].is_empty() {
            Vec::new()
        } else {
            parts[3].split(',').map(|s| s.to_string()).collect()
        };

        out.push(Entry {
            name,
            age,
            active,
            tags,
        });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "Alice|34|true|admin,ops\nBob|0|false|\nCara|99|true|qa";
        let got = parse_entries(input).unwrap();
        assert_eq!(
            got,
            vec![
                Entry {
                    name: "Alice".into(),
                    age: 34,
                    active: true,
                    tags: vec!["admin".into(), "ops".into()],
                },
                Entry {
                    name: "Bob".into(),
                    age: 0,
                    active: false,
                    tags: vec![],
                },
                Entry {
                    name: "Cara".into(),
                    age: 99,
                    active: true,
                    tags: vec!["qa".into()],
                },
            ]
        );
    }

    #[test]
    fn trims_fields_and_skips_comment_lines() {
        let input = "  # comment\n  Dana  | 7 | false | red, blue \n\n# another";
        let got = parse_entries(input).unwrap();
        assert_eq!(
            got,
            vec![Entry {
                name: "Dana".into(),
                age: 7,
                active: false,
                tags: vec!["red".into(), "blue".into()],
            }]
        );
    }

    #[test]
    fn rejects_extra_or_missing_fields() {
        let err1 = parse_entries("Eli|5|true").unwrap_err();
        assert_eq!(err1, "line 1: expected 4 fields");

        let err2 = parse_entries("Eli|5|true|x|y").unwrap_err();
        assert_eq!(err2, "line 1: expected 4 fields");
    }

    #[test]
    fn validates_name_age_and_tags() {
        assert_eq!(
            parse_entries(" |5|true|x").unwrap_err(),
            "line 1: empty name"
        );
        assert_eq!(
            parse_entries("Eli|120|true|x").unwrap_err(),
            "line 1: age out of range"
        );
        assert_eq!(
            parse_entries("Eli|5|true|x,,y").unwrap_err(),
            "line 1: empty tag"
        );
        assert_eq!(
            parse_entries("Eli|5|true|x,x").unwrap_err(),
            "line 1: duplicate tag 'x'"
        );
    }

    #[test]
    fn active_flag_is_case_insensitive() {
        let got = parse_entries("Fran|44|TRUE|solo").unwrap();
        assert_eq!(got[0].active, true);
    }
}
