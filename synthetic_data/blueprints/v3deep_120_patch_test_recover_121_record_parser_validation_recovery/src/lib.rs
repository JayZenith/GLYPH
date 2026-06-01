pub fn validate_batch(input: &str) -> Result<Vec<(String, u8, Vec<String>)>, String> {
    let mut out = Vec::new();
    for (idx, line) in input.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() != 3 {
            return Err(format!("line {}: expected 3 fields", idx + 1));
        }

        let name = parts[0].to_string();
        if name.is_empty() {
            return Err(format!("line {}: empty name", idx + 1));
        }

        let score: u8 = parts[1]
            .parse()
            .map_err(|_| format!("line {}: invalid score", idx + 1))?;

        let tags: Vec<String> = parts[2]
            .split(',')
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .collect();

        if tags.is_empty() {
            return Err(format!("line {}: no tags", idx + 1));
        }

        out.push((name, score, tags));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::validate_batch;

    #[test]
    fn parses_valid_rows_and_trims_fields() {
        let rows = validate_batch(" alice |42| red, blue \nBob|7|solo").unwrap();
        assert_eq!(rows[0].0, "alice");
        assert_eq!(rows[0].1, 42);
        assert_eq!(rows[0].2, vec!["red", "blue"]);
        assert_eq!(rows[1], ("Bob".to_string(), 7, vec!["solo".to_string()]));
    }

    #[test]
    fn rejects_score_out_of_range() {
        let err = validate_batch("alice|101|x").unwrap_err();
        assert_eq!(err, "line 1: score out of range");
    }

    #[test]
    fn rejects_duplicate_tags_case_insensitively() {
        let err = validate_batch("alice|8|red,Red").unwrap_err();
        assert_eq!(err, "line 1: duplicate tag 'Red'");
    }

    #[test]
    fn rejects_non_alphanumeric_tag_characters() {
        let err = validate_batch("alice|8|ok,bad-tag").unwrap_err();
        assert_eq!(err, "line 1: invalid tag 'bad-tag'");
    }
}
