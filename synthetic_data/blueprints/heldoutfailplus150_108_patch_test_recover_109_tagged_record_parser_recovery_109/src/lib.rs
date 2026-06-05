#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub id: u32,
    pub tag: String,
    pub value: i32,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();
    for (line_no, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }

        let mut name = None;
        let mut id = None;
        let mut tag = None;
        let mut value = None;

        for part in line.split('|') {
            let mut kv = part.splitn(2, '=');
            let key = kv.next().unwrap_or("").trim();
            let val = kv.next().unwrap_or("").trim();
            match key {
                "name" => name = Some(val.to_string()),
                "id" => id = val.parse::<u32>().ok(),
                "tag" => tag = Some(val.to_string()),
                "value" => value = val.parse::<i32>().ok(),
                _ => {}
            }
        }

        if let (Some(name), Some(id), Some(tag), Some(value)) = (name, id, tag, value) {
            out.push(Record { name, id, tag, value });
        } else {
            return Err(format!("line {} invalid", line_no + 1));
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "name=alpha|id=10|tag=core|value=5\nname=beta|id=11|tag=aux|value=-2";
        let records = parse_records(input).unwrap();
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].name, "alpha");
        assert_eq!(records[1].value, -2);
    }

    #[test]
    fn rejects_missing_or_malformed_fields() {
        let missing = "name=alpha|id=10|tag=core";
        assert_eq!(parse_records(missing), Err("line 1 invalid".to_string()));

        let bad_id = "name=alpha|id=nope|tag=core|value=5";
        assert_eq!(parse_records(bad_id), Err("line 1 invalid".to_string()));

        let malformed = "name=alpha|id=10|tag|value=5";
        assert_eq!(parse_records(malformed), Err("line 1 invalid".to_string()));
    }

    #[test]
    fn rejects_duplicate_and_unknown_keys() {
        let dup = "name=alpha|id=10|tag=core|value=5|tag=aux";
        assert_eq!(parse_records(dup), Err("line 1 invalid".to_string()));

        let unknown = "name=alpha|id=10|tag=core|value=5|extra=x";
        assert_eq!(parse_records(unknown), Err("line 1 invalid".to_string()));
    }

    #[test]
    fn validates_name_tag_and_value_rules() {
        let empty_name = "name=|id=10|tag=core|value=5";
        assert_eq!(parse_records(empty_name), Err("line 1 invalid".to_string()));

        let bad_name = "name=Alpha1|id=10|tag=core|value=5";
        assert_eq!(parse_records(bad_name), Err("line 1 invalid".to_string()));

        let bad_tag = "name=alpha|id=10|tag=CORE|value=5";
        assert_eq!(parse_records(bad_tag), Err("line 1 invalid".to_string()));

        let bad_value = "name=alpha|id=10|tag=core|value=2000";
        assert_eq!(parse_records(bad_value), Err("line 1 invalid".to_string()));
    }

    #[test]
    fn rejects_non_increasing_ids_across_lines() {
        let input = "name=alpha|id=10|tag=core|value=5\nname=beta|id=10|tag=aux|value=6";
        assert_eq!(parse_records(input), Err("line 2 invalid".to_string()));
    }
}
