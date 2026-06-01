#[derive(Debug, PartialEq, Eq)]
pub struct Entry {
    pub id: u32,
    pub kind: String,
    pub active: bool,
    pub score: u8,
}

pub fn parse_entry(line: &str) -> Result<Entry, String> {
    let mut id = None;
    let mut kind = None;
    let mut active = None;
    let mut score = None;

    for part in line.split('|') {
        if part.is_empty() {
            continue;
        }
        let Some((key, value)) = part.split_once('=') else {
            continue;
        };
        match key {
            "id" => {
                id = value.parse::<u32>().ok();
            }
            "kind" => {
                kind = Some(value.to_string());
            }
            "active" => {
                active = Some(matches!(value, "true" | "yes" | "1"));
            }
            "score" => {
                score = value.parse::<u8>().ok();
            }
            _ => {}
        }
    }

    let id = id.ok_or_else(|| "missing id".to_string())?;
    let kind = kind.ok_or_else(|| "missing kind".to_string())?;
    let active = active.ok_or_else(|| "missing active".to_string())?;
    let score = score.unwrap_or(0);

    Ok(Entry { id, kind, active, score })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record() {
        let got = parse_entry("id=7|kind=beta|active=true|score=42").unwrap();
        assert_eq!(
            got,
            Entry {
                id: 7,
                kind: "beta".to_string(),
                active: true,
                score: 42,
            }
        );
    }

    #[test]
    fn rejects_unknown_field() {
        let err = parse_entry("id=7|kind=beta|active=true|score=42|extra=nope").unwrap_err();
        assert_eq!(err, "unknown field: extra");
    }

    #[test]
    fn rejects_duplicate_field() {
        let err = parse_entry("id=7|kind=beta|active=true|score=42|kind=gamma").unwrap_err();
        assert_eq!(err, "duplicate field: kind");
    }

    #[test]
    fn rejects_invalid_active_value() {
        let err = parse_entry("id=7|kind=beta|active=maybe|score=42").unwrap_err();
        assert_eq!(err, "invalid active");
    }

    #[test]
    fn rejects_out_of_range_score() {
        let err = parse_entry("id=7|kind=beta|active=true|score=120").unwrap_err();
        assert_eq!(err, "score out of range");
    }

    #[test]
    fn rejects_empty_kind() {
        let err = parse_entry("id=7|kind=|active=true|score=42").unwrap_err();
        assert_eq!(err, "empty kind");
    }
}
