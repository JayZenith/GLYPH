#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub id: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_record(line: &str) -> Result<Record, String> {
    let mut id = None;
    let mut qty = None;
    let mut active = None;

    for part in line.split(',') {
        let mut pieces = part.split('=');
        let key = pieces.next().ok_or_else(|| "missing key".to_string())?;
        let value = pieces.next().ok_or_else(|| format!("missing value for {key}"))?;

        match key {
            "id" => id = Some(value.to_string()),
            "qty" => qty = Some(value.parse::<u32>().map_err(|_| "bad qty".to_string())?),
            "active" => active = Some(value == "true"),
            _ => {}
        }
    }

    Ok(Record {
        id: id.ok_or_else(|| "missing id".to_string())?,
        qty: qty.ok_or_else(|| "missing qty".to_string())?,
        active: active.ok_or_else(|| "missing active".to_string())?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_fields_in_any_order() {
        let rec = parse_record("active=true,qty=7,id=item_42").unwrap();
        assert_eq!(
            rec,
            Record {
                id: "item_42".to_string(),
                qty: 7,
                active: true,
            }
        );
    }

    #[test]
    fn rejects_spaces_inside_id() {
        assert_eq!(
            parse_record("id=bad id,qty=1,active=false"),
            Err("bad id".to_string())
        );
    }

    #[test]
    fn rejects_non_positive_qty() {
        assert_eq!(
            parse_record("id=widget,qty=0,active=true"),
            Err("bad qty".to_string())
        );
    }

    #[test]
    fn rejects_invalid_active_value() {
        assert_eq!(
            parse_record("id=widget,qty=3,active=yes"),
            Err("bad active".to_string())
        );
    }

    #[test]
    fn rejects_unknown_field() {
        assert_eq!(
            parse_record("id=widget,qty=3,active=true,color=red"),
            Err("unknown field".to_string())
        );
    }
}
