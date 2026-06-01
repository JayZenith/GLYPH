use std::collections::HashSet;

#[derive(Debug, PartialEq, Eq)]
pub struct Entry {
    pub id: u32,
    pub kind: String,
    pub enabled: bool,
    pub tags: Vec<String>,
}

pub fn parse_entries(input: &str) -> Result<Vec<Entry>, String> {
    let mut out = Vec::new();
    let mut ids = HashSet::new();

    for (line_no, raw_line) in input.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let mut id = None;
        let mut kind = None;
        let mut enabled = false;
        let mut tags: Vec<String> = Vec::new();

        for part in line.split(';') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }
            let mut kv = part.splitn(2, '=');
            let key = kv.next().unwrap().trim();
            let value = kv.next().unwrap_or("").trim();
            match key {
                "id" => {
                    id = value.parse::<u32>().ok();
                }
                "kind" => {
                    kind = Some(value.to_string());
                }
                "enabled" => {
                    enabled = value == "true" || value == "yes" || value == "1";
                }
                "tags" => {
                    tags = value
                        .split(',')
                        .filter(|s| !s.is_empty())
                        .map(|s| s.to_string())
                        .collect();
                }
                _ => {}
            }
        }

        let id = id.ok_or_else(|| format!("line {}: missing id", line_no + 1))?;
        if !ids.insert(id) {
            return Err(format!("line {}: duplicate id {}", line_no + 1, id));
        }
        let kind = kind.ok_or_else(|| format!("line {}: missing kind", line_no + 1))?;

        out.push(Entry {
            id,
            kind,
            enabled,
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
        let input = "id=1; kind=alpha; enabled=true; tags=red,blue\n\
                     id=2; kind=beta; enabled=false; tags=green";
        let got = parse_entries(input).unwrap();
        assert_eq!(
            got,
            vec![
                Entry {
                    id: 1,
                    kind: "alpha".into(),
                    enabled: true,
                    tags: vec!["red".into(), "blue".into()],
                },
                Entry {
                    id: 2,
                    kind: "beta".into(),
                    enabled: false,
                    tags: vec!["green".into()],
                }
            ]
        );
    }

    #[test]
    fn rejects_unknown_keys() {
        let err = parse_entries("id=1; kind=alpha; extra=nope").unwrap_err();
        assert_eq!(err, "line 1: unknown field extra");
    }

    #[test]
    fn rejects_invalid_boolean() {
        let err = parse_entries("id=1; kind=alpha; enabled=maybe").unwrap_err();
        assert_eq!(err, "line 1: invalid enabled maybe");
    }

    #[test]
    fn rejects_uppercase_kind() {
        let err = parse_entries("id=1; kind=Alpha").unwrap_err();
        assert_eq!(err, "line 1: invalid kind Alpha");
    }

    #[test]
    fn rejects_bad_tags() {
        let err = parse_entries("id=1; kind=alpha; tags=red,blue-1").unwrap_err();
        assert_eq!(err, "line 1: invalid tag blue-1");
    }

    #[test]
    fn rejects_duplicate_tags_after_trimming() {
        let err = parse_entries("id=1; kind=alpha; tags=red, blue ,red").unwrap_err();
        assert_eq!(err, "line 1: duplicate tag red");
    }
}
