pub fn extract_allowed_scores(items: &[&str], limit: i32) -> Vec<(String, i32)> {
    items
        .iter()
        .filter_map(|line| {
            let (name, value) = line.split_once(':')?;
            let score = value.parse::<i32>().ok()?;
            if score <= limit {
                return None;
            }
            Some((name.to_string(), score))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::extract_allowed_scores;

    #[test]
    fn keeps_even_scores_within_limit_and_trims_name() {
        let items = [" alice : 4", "bob:3", "cara:8", "drew:7", "erin:10"];
        let got = extract_allowed_scores(&items, 8);
        assert_eq!(got, vec![("alice".to_string(), 4), ("cara".to_string(), 8)]);
    }

    #[test]
    fn skips_invalid_negative_and_empty_name_entries() {
        let items = ["zoe:-2", ":6", "ian:5", "maya:12", "nope", "ava:2"];
        let got = extract_allowed_scores(&items, 10);
        assert_eq!(got, vec![("ava".to_string(), 2)]);
    }

    #[test]
    fn preserves_input_order_for_valid_entries() {
        let items = ["one:6", "two:4", "three:9", "four:8"];
        let got = extract_allowed_scores(&items, 8);
        assert_eq!(got, vec![("one".to_string(), 6), ("two".to_string(), 4), ("four".to_string(), 8)]);
    }
}
