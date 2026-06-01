#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() < 3 {
        return Err("expected 3 fields".into());
    }

    let name = parts[0].to_string();
    if name.is_empty() {
        return Err("name missing".into());
    }

    let qty = parts[1].parse::<u32>().map_err(|_| "invalid qty".to_string())?;
    let active = match parts[2] {
        "true" => true,
        "false" => false,
        _ => return Err("invalid active".into()),
    };

    Ok(Record { name, qty, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_record_with_trimming() {
        let rec = parse_record(" apples , 12 , true ").unwrap();
        assert_eq!(rec, Record {
            name: "apples".into(),
            qty: 12,
            active: true,
        });
    }

    #[test]
    fn rejects_wrong_field_count() {
        assert_eq!(parse_record("a,1,true,extra"), Err("expected 3 fields".into()));
        assert_eq!(parse_record("a,1"), Err("expected 3 fields".into()));
    }

    #[test]
    fn rejects_blank_name_after_trim() {
        assert_eq!(parse_record("   ,2,false"), Err("name missing".into()));
    }

    #[test]
    fn rejects_zero_qty() {
        assert_eq!(parse_record("pears,0,true"), Err("qty must be positive".into()));
    }

    #[test]
    fn accepts_yes_no_for_active_case_insensitive() {
        let rec = parse_record("pears,5,YeS").unwrap();
        assert_eq!(rec.active, true);
        let rec = parse_record("pears,5,no").unwrap();
        assert_eq!(rec.active, false);
    }
}
