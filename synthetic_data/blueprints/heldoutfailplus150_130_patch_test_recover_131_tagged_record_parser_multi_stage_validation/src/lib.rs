#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub id: String,
    pub kind: String,
    pub score: u32,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for (line_no, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut id = None;
        let mut kind = None;
        let mut score = 0;
        let mut active = false;

        for part in line.split(';') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }

            let Some((tag, value)) = part.split_once(':') else {
                return Err(format!("line {} malformed field", line_no + 1));
            };

            match tag.trim() {
                "id" => id = Some(value.trim().to_string()),
                "kind" => kind = Some(value.trim().to_string()),
                "score" => score = value.trim().parse::<u32>().unwrap_or(0),
                "active" => active = value.trim() == "true",
                _ => {}
            }
        }

        let id = id.ok_or_else(|| format!("line {} missing id", line_no + 1))?;
        let kind = kind.unwrap_or_else(|| "misc".to_string());

        out.push(Record {
            id,
            kind,
            score,
            active,
        });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "id:A1;kind:alpha;score:7;active:true\nid:B2;kind:beta;score:0;active:false";
        let got = parse_records(input).unwrap();
        assert_eq!(got.len(), 2);
        assert_eq!(
            got[0],
            Record {
                id: "A1".into(),
                kind: "alpha".into(),
                score: 7,
                active: true,
            }
        );
        assert_eq!(got[1].id, "B2");
        assert_eq!(got[1].kind, "beta");
        assert_eq!(got[1].score, 0);
        assert!(!got[1].active);
    }

    #[test]
    fn rejects_missing_required_kind() {
        let err = parse_records("id:A1;score:3;active:true").unwrap_err();
        assert_eq!(err, "line 1 missing kind");
    }

    #[test]
    fn rejects_unknown_tag() {
        let err = parse_records("id:A1;kind:alpha;score:3;active:true;extra:nope").unwrap_err();
        assert_eq!(err, "line 1 unknown tag extra");
    }

    #[test]
    fn rejects_duplicate_tag() {
        let err = parse_records("id:A1;kind:alpha;kind:beta;score:3;active:true").unwrap_err();
        assert_eq!(err, "line 1 duplicate tag kind");
    }

    #[test]
    fn rejects_bad_score_values() {
        let err = parse_records("id:A1;kind:alpha;score:abc;active:true").unwrap_err();
        assert_eq!(err, "line 1 invalid score abc");

        let err = parse_records("id:A1;kind:alpha;score:101;active:true").unwrap_err();
        assert_eq!(err, "line 1 score out of range 101");
    }

    #[test]
    fn rejects_bad_active_values() {
        let err = parse_records("id:A1;kind:alpha;score:3;active:yes").unwrap_err();
        assert_eq!(err, "line 1 invalid active yes");
    }

    #[test]
    fn rejects_empty_required_values() {
        let err = parse_records("id: ;kind:alpha;score:3;active:true").unwrap_err();
        assert_eq!(err, "line 1 empty value for id");

        let err = parse_records("id:A1;kind: ;score:3;active:true").unwrap_err();
        assert_eq!(err, "line 1 empty value for kind");
    }

    #[test]
    fn rejects_field_without_separator() {
        let err = parse_records("id:A1;kind:alpha;broken;score:3;active:true").unwrap_err();
        assert_eq!(err, "line 1 malformed field broken");
    }
}
