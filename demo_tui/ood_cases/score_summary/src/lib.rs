#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ScoreSummary {
    pub submitted_count: usize,
    pub total_points: u32,
    pub best_score: u32,
}

pub fn summarize_scores(scores: &[i32]) -> ScoreSummary {
    let mut submitted_count = 0;
    let mut total_points = 0;
    let mut best_score = 0;

    for score in scores {
        submitted_count += 1;
        let normalized = *score as u32;
        total_points += normalized;
        if normalized > best_score {
            best_score = normalized;
        }
    }

    ScoreSummary {
        submitted_count,
        total_points,
        best_score,
    }
}

#[cfg(test)]
mod tests {
    use super::{summarize_scores, ScoreSummary};

    #[test]
    fn summarizes_normal_scores() {
        let summary = summarize_scores(&[10, 20, 30]);

        assert_eq!(
            summary,
            ScoreSummary {
                submitted_count: 3,
                total_points: 60,
                best_score: 30,
            }
        );
    }

    #[test]
    fn ignores_negative_scores() {
        let summary = summarize_scores(&[10, -5, 30, -1]);

        assert_eq!(summary.submitted_count, 2);
        assert_eq!(summary.total_points, 40);
        assert_eq!(summary.best_score, 30);
    }

    #[test]
    fn caps_scores_above_one_hundred() {
        let summary = summarize_scores(&[80, 120, 101]);

        assert_eq!(summary.submitted_count, 3);
        assert_eq!(summary.total_points, 280);
        assert_eq!(summary.best_score, 100);
    }

    #[test]
    fn empty_or_all_invalid_scores_have_zero_summary() {
        assert_eq!(
            summarize_scores(&[]),
            ScoreSummary {
                submitted_count: 0,
                total_points: 0,
                best_score: 0,
            }
        );
        assert_eq!(
            summarize_scores(&[-10, -1]),
            ScoreSummary {
                submitted_count: 0,
                total_points: 0,
                best_score: 0,
            }
        );
    }
}
