#[derive(Debug, PartialEq, Eq)]
pub struct Record {
    pub name: String,
    pub qty: u32,
    pub active: bool,
}

pub fn parse_records(input: &str) -> Result<Vec<Record>, String> {
    let mut out = Vec::new();

    for block in input.split("\n\n") {
        if block.is_empty() {
            continue;
        }

        let mut name = String::new();
        let mut qty = 0u32;
        let mut active = false;

        for line in block.lines() {
            let Some((key, value)) = line.split_once(':') else {
                return Err("invalid line".into());
            };

            match key {
                "name" => name = value.to_string(),
                "qty" => qty = value.parse::<u32>().map_err(|_| "bad qty")?,
                "active" => active = value == "true",
                _ => {}
            }
        }

        out.push(Record { name, qty, active });
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_records() {
        let input = "name:Widget\nqty:10\nactive:true\n\nname:Gadget\nqty:0\nactive:false";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![
                Record {
                    name: "Widget".into(),
                    qty: 10,
                    active: true,
                },
                Record {
                    name: "Gadget".into(),
                    qty: 0,
                    active: false,
                }
            ]
        );
    }

    #[test]
    fn trims_space_around_values() {
        let input = "name: Widget \nqty: 7\nactive: false ";
        let got = parse_records(input).unwrap();
        assert_eq!(
            got,
            vec![Record {
                name: "Widget".into(),
                qty: 7,
                active: false,
            }]
        );
    }

    #[test]
    fn rejects_missing_required_field() {
        let input = "name:Widget\nactive:true";
        assert!(parse_records(input).is_err());
    }

    #[test]
    fn rejects_unknown_keys() {
        let input = "name:Widget\nqty:1\nactive:true\ncolor:red";
        assert!(parse_records(input).is_err());
    }

    #[test]
    fn rejects_invalid_boolean_text() {
        let input = "name:Widget\nqty:1\nactive:yes";
        assert!(parse_records(input).is_err());
    }

    #[test]
    fn rejects_blank_name() {
        let input = "name:   \nqty:1\nactive:true";
        assert!(parse_records(input).is_err());
    }
}
