pub fn parse_valid_ids(input: &str) -> Vec<String> {
    let mut out = Vec::new();

    for line in input.lines() {
        if line.is_empty() {
            continue;
        }

        let mut id = "";
        let mut qty = 0u32;
        let mut active = false;

        for part in line.split(';') {
            let mut it = part.split('=');
            let key = it.next().unwrap_or("");
            let value = it.next().unwrap_or("");
            match key {
                "id" => id = value,
                "qty" => qty = value.parse::<u32>().unwrap_or(0),
                "active" => active = value == "true",
                _ => {}
            }
        }

        if !id.is_empty() && qty > 0 && active {
            out.push(id.to_string());
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::parse_valid_ids;

    #[test]
    fn accepts_only_fully_valid_records() {
        let input = "id=A1;qty=3;active=true\n\
                     id=;qty=8;active=true\n\
                     qty=5;active=true\n\
                     id=B2;qty=0;active=true\n\
                     id=C3;qty=7;active=false\n\
                     id=D4;qty=2;active=true";
        assert_eq!(parse_valid_ids(input), vec!["A1", "D4"]);
    }

    #[test]
    fn trims_spaces_and_ignores_blank_lines() {
        let input = "  id = X1 ; qty = 4 ; active = true  \n\
                     \n\
                       id=Y2; qty=1; active=true   \n";
        assert_eq!(parse_valid_ids(input), vec!["X1", "Y2"]);
    }

    #[test]
    fn rejects_duplicate_keys_and_extra_equals() {
        let input = "id=A1;qty=2;active=true\n\
                     id=B2;qty=2;qty=3;active=true\n\
                     id=C3;qty=4=5;active=true\n\
                     id=D4;qty=6;active=true";
        assert_eq!(parse_valid_ids(input), vec!["A1", "D4"]);
    }

    #[test]
    fn field_order_does_not_matter() {
        let input = "active=true;qty=9;id=Q9\n\
                     qty=1;id=R1;active=true";
        assert_eq!(parse_valid_ids(input), vec!["Q9", "R1"]);
    }
}
