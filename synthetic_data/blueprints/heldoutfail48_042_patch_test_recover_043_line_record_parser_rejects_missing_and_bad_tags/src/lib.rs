use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub name: String,
    pub tags: Vec<String>,
    pub score: u8,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (line_no, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut fields: HashMap<&str, &str> = HashMap::new();
        for part in line.split(';') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }
            let (key, value) = part
                .split_once('=')
                .ok_or_else(|| format!("line {} malformed field", line_no + 1))?;
            fields.insert(key.trim(), value.trim());
        }

        let id = fields
            .get("id")
            .ok_or_else(|| format!("line {} missing id", line_no + 1))?
            .parse::<u32>()
            .map_err(|_| format!("line {} bad id", line_no + 1))?;

        let name = fields.get("name").copied().unwrap_or("").to_string();

        let tags = fields
            .get("tags")
            .map(|s| {
                s.split(',')
                    .filter(|t| !t.is_empty())
                    .map(|t| t.to_string())
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();

        let score = fields
            .get("score")
            .copied()
            .unwrap_or("0")
            .parse::<u8>()
            .map_err(|_| format!("line {} bad score", line_no + 1))?;

        out.push(Record {
            id,
            name,
            tags,
            score,
        });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "id=1;name=Alpha;tags=red,blue;score=7\nid=2;name=Beta;tags=solo;score=0";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    id: 1,
                    name: "Alpha".into(),
                    tags: vec!["red".into(), "blue".into()],
                    score: 7,
                },
                Record {
                    id: 2,
                    name: "Beta".into(),
                    tags: vec!["solo".into()],
                    score: 0,
                }
            ]
        );
    }

    #[test]
    fn requires_name_and_score_fields() {
        let err = parse_records("id=3;tags=x").unwrap_err();
        assert_eq!(err, "line 1 missing name");

        let err = parse_records("id=3;name=Gamma;tags=x").unwrap_err();
        assert_eq!(err, "line 1 missing score");
    }

    #[test]
    fn rejects_unknown_or_duplicate_fields() {
        let err = parse_records("id=1;name=A;score=1;extra=z").unwrap_err();
        assert_eq!(err, "line 1 unknown field extra");

        let err = parse_records("id=1;name=A;score=1;name=B").unwrap_err();
        assert_eq!(err, "line 1 duplicate field name");
    }

    #[test]
    fn rejects_empty_name_and_out_of_range_score() {
        let err = parse_records("id=1;name=;score=2").unwrap_err();
        assert_eq!(err, "line 1 empty name");

        let err = parse_records("id=1;name=A;score=11").unwrap_err();
        assert_eq!(err, "line 1 score out of range");
    }

    #[test]
    fn validates_tags_nonempty_unique_and_lowercase_ascii() {
        let err = parse_records("id=1;name=A;score=3;tags=ok,,bad").unwrap_err();
        assert_eq!(err, "line 1 empty tag");

        let err = parse_records("id=1;name=A;score=3;tags=dup,dup").unwrap_err();
        assert_eq!(err, "line 1 duplicate tag dup");

        let err = parse_records("id=1;name=A;score=3;tags=ok,Bad").unwrap_err();
        assert_eq!(err, "line 1 invalid tag Bad");

        let err = parse_records("id=1;name=A;score=3;tags=ok,bad-tag").unwrap_err();
        assert_eq!(err, "line 1 invalid tag bad-tag");
    }

    #[test]
    fn malformed_field_without_equals_is_rejected() {
        let err = parse_records("id=1;name=A;score=3;tags").unwrap_err();
        assert_eq!(err, "line 1 malformed field");
    }
}
