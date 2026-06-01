pub fn collect_scores(rows: &[&str]) -> Vec<(String, u32)> {
    rows.iter()
        .filter_map(|row| {
            let mut parts = row.split('|');
            let name = parts.next()?;
            let status = parts.next()?;
            let score = parts.next()?.parse::<u32>().ok()?;
            if status == "active" {
                Some((name.to_string(), score))
            } else {
                None
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_scores;

    #[test]
    fn keeps_only_active_rows_with_clean_names_and_valid_positive_scores() {
        let rows = [
            " alice |active|10",
            "bob|inactive|7",
            "carol|active|0",
            "dave|active|-3",
            "eve|active|8|extra",
            " frank|active| 12 ",
        ];
        assert_eq!(collect_scores(&rows), vec![
            ("alice".to_string(), 10),
            ("frank".to_string(), 12),
        ]);
    }

    #[test]
    fn ignores_rows_with_wrong_field_count_or_blank_name() {
        let rows = [
            "|active|5",
            "gina|active",
            "henry|active|9|bonus",
            "ivy|active|3",
        ];
        assert_eq!(collect_scores(&rows), vec![("ivy".to_string(), 3)]);
    }

    #[test]
    fn preserves_input_order_for_surviving_rows() {
        let rows = [
            "zoe|active|2",
            "amy|active|4",
            "max|inactive|9",
            "ian|active|1",
        ];
        assert_eq!(collect_scores(&rows), vec![
            ("zoe".to_string(), 2),
            ("amy".to_string(), 4),
            ("ian".to_string(), 1),
        ]);
    }
}
