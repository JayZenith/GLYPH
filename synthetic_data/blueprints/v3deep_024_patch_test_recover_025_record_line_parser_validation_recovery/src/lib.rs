#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub key: String,
    pub count: u32,
    pub enabled: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut parts = line.split('|');
    let key = parts.next().ok_or_else(|| "missing key".to_string())?.to_string();
    let count_str = parts.next().ok_or_else(|| "missing count".to_string())?;
    let enabled_str = parts.next().ok_or_else(|| "missing enabled".to_string())?;

    let count = count_str.parse::<u32>().map_err(|_| "invalid count".to_string())?;
    let enabled = match enabled_str {
        "true" => true,
        "false" => false,
        _ => return Err("invalid enabled".to_string()),
    };

    Ok(Record { key, count, enabled })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_trimmed_fields() {
        let rec = parse_record("  alpha_1 | 42 | true ").unwrap();
        assert_eq!(
            rec,
            Record {
                key: "alpha_1".to_string(),
                count: 42,
                enabled: true,
            }
        );
    }

    #[test]
    fn rejects_extra_field() {
        let err = parse_record("alpha|3|false|extra").unwrap_err();
        assert_eq!(err, "wrong field count");
    }

    #[test]
    fn rejects_bad_key_shape() {
        let err = parse_record("Alpha-1|3|true").unwrap_err();
        assert_eq!(err, "invalid key");
    }

    #[test]
    fn rejects_zero_count() {
        let err = parse_record("alpha|0|false").unwrap_err();
        assert_eq!(err, "invalid count");
    }

    #[test]
    fn rejects_non_bool_even_with_spaces() {
        let err = parse_record("alpha|5| yes ").unwrap_err();
        assert_eq!(err, "invalid enabled");
    }
}
