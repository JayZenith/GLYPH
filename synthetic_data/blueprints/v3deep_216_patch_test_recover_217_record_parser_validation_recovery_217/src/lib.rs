#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: u32,
    pub kind: String,
    pub active: bool,
    pub tags: Vec<String>,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (line_no, raw_line) in input.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }

        let mut id = None;
        let mut kind = None;
        let mut active = None;
        let mut tags: Vec<String> = Vec::new();

        for part in line.split(';') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }
            let (key, value) = part
                .split_once('=')
                .ok_or_else(|| format!("line {}: bad field", line_no + 1))?;
            match key.trim() {
                "id" => {
                    id = Some(value.trim().parse::<u32>().map_err(|_| {
                        format!("line {}: invalid id", line_no + 1)
                    })?);
                }
                "kind" => kind = Some(value.trim().to_string()),
                "active" => {
                    active = Some(match value.trim() {
                        "true" => true,
                        "false" => false,
                        _ => return Err(format!("line {}: invalid active", line_no + 1)),
                    });
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

        out.push(Record {
            id: id.ok_or_else(|| format!("line {}: missing id", line_no + 1))?,
            kind: kind.ok_or_else(|| format!("line {}: missing kind", line_no + 1))?,
            active: active.unwrap_or(false),
            tags,
        });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records_and_trims_tag_items() {
        let input = "id=1; kind=alpha; active=true; tags=red, blue\nid=2; kind=beta; active=false; tags=solo";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    id: 1,
                    kind: "alpha".to_string(),
                    active: true,
                    tags: vec!["red".to_string(), "blue".to_string()],
                },
                Record {
                    id: 2,
                    kind: "beta".to_string(),
                    active: false,
                    tags: vec!["solo".to_string()],
                }
            ]
        );
    }

    #[test]
    fn rejects_unknown_field() {
        let err = parse_records("id=1; kind=alpha; active=true; extra=nope").unwrap_err();
        assert_eq!(err, "line 1: unknown field extra");
    }

    #[test]
    fn rejects_duplicate_field() {
        let err = parse_records("id=1; kind=alpha; kind=beta; active=true").unwrap_err();
        assert_eq!(err, "line 1: duplicate field kind");
    }

    #[test]
    fn rejects_missing_active() {
        let err = parse_records("id=1; kind=alpha").unwrap_err();
        assert_eq!(err, "line 1: missing active");
    }

    #[test]
    fn rejects_out_of_range_id() {
        let err = parse_records("id=0; kind=alpha; active=true").unwrap_err();
        assert_eq!(err, "line 1: id out of range");
        let err = parse_records("id=10000; kind=alpha; active=true").unwrap_err();
        assert_eq!(err, "line 1: id out of range");
    }

    #[test]
    fn rejects_invalid_kind_format() {
        let err = parse_records("id=5; kind=Alpha-1; active=true").unwrap_err();
        assert_eq!(err, "line 1: invalid kind");
    }

    #[test]
    fn rejects_duplicate_tags() {
        let err = parse_records("id=5; kind=alpha; active=true; tags=red,blue,red").unwrap_err();
        assert_eq!(err, "line 1: duplicate tag red");
    }
}
