pub fn collect_even_scores(lines: &[&str]) -> Vec<String> {
    lines
        .iter()
        .filter_map(|line| {
            let (name, value) = line.split_once(':')?;
            let score = value.parse::<i32>().ok()?;
            if score % 2 == 0 {
                Some(format!("{}={}", name.trim(), score))
            } else {
                None
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_even_scores;

    #[test]
    fn keeps_even_scores_in_input_order() {
        let input = ["alice:2", "bob:3", "cara:4"];
        assert_eq!(collect_even_scores(&input), vec!["alice=2", "cara=4"]);
    }

    #[test]
    fn trims_name_and_requires_positive_even_scores() {
        let input = ["  alice  :2", "bob:0", "cara:-4", "dave:6"];
        assert_eq!(collect_even_scores(&input), vec!["alice=2", "dave=6"]);
    }

    #[test]
    fn ignores_blank_names_and_invalid_numbers() {
        let input = [":8", "   :10", "ok:12", "bad:xx", "no_colon"];
        assert_eq!(collect_even_scores(&input), vec!["ok=12"]);
    }

    #[test]
    fn skips_duplicate_names_after_trimming_case_insensitively() {
        let input = ["Alice:2", " alice :8", "BOB:4", "bob:10", "Cara:6"];
        assert_eq!(collect_even_scores(&input), vec!["Alice=2", "BOB=4", "Cara=6"]);
    }
}
