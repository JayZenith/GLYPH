#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Event<'a> {
    pub id: u32,
    pub source: &'a str,
    pub category: &'a str,
    pub title: &'a str,
    pub active: bool,
    pub score: i32,
    pub tags: &'a [&'a str],
}

pub fn curated_titles(events: &[Event<'_>], blocked_sources: &[&str]) -> Vec<String> {
    let mut items: Vec<(i32, String)> = events
        .iter()
        .filter(|e| e.active)
        .filter(|e| e.score >= 50)
        .filter(|e| !blocked_sources.iter().any(|s| *s == e.source))
        .filter(|e| !e.title.trim().is_empty())
        .map(|e| (e.score, format!("{}: {}", e.category, e.title.trim())))
        .collect();

    items.sort_by(|a, b| b.0.cmp(&a.0));
    items.into_iter().map(|(_, s)| s).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample<'a>() -> Vec<Event<'a>> {
        vec![
            Event { id: 1, source: "feed-a", category: "ops", title: "Disk Full", active: true, score: 80, tags: &["urgent", "infra"] },
            Event { id: 2, source: "feed-b", category: "ops", title: "Disk Full", active: true, score: 83, tags: &["infra"] },
            Event { id: 3, source: "feed-a", category: "ops", title: "   ", active: true, score: 95, tags: &["urgent"] },
            Event { id: 4, source: "feed-c", category: "news", title: "Release", active: true, score: 76, tags: &["public"] },
            Event { id: 5, source: "feed-d", category: "ops", title: "CPU Spike", active: false, score: 90, tags: &["urgent"] },
            Event { id: 6, source: "feed-e", category: "ops", title: "Memory Leak", active: true, score: 60, tags: &["ignore", "urgent"] },
            Event { id: 7, source: "feed-f", category: "ops", title: "Cache Miss", active: true, score: 76, tags: &[] },
            Event { id: 8, source: "feed-g", category: "ops", title: "Disk Full", active: true, score: 83, tags: &["urgent"] },
            Event { id: 9, source: "feed-z", category: "ops", title: "Ghost", active: true, score: 99, tags: &["urgent"] },
            Event { id: 10, source: "feed-h", category: "ops", title: "Nightly Backup", active: true, score: 50, tags: &["urgent"] },
            Event { id: 11, source: "feed-i", category: "ops", title: "Kernel Panic", active: true, score: 76, tags: &["urgent"] },
            Event { id: 12, source: "feed-j", category: "ops", title: "Muted Alert", active: true, score: 88, tags: &["ignore"] },
        ]
    }

    #[test]
    fn excludes_blocked_low_quality_and_ignored_items() {
        let events = sample();
        let got = curated_titles(&events, &["feed-z"]);
        assert_eq!(
            got,
            vec![
                "ops: Disk Full".to_string(),
                "ops: Kernel Panic".to_string(),
                "ops: Nightly Backup".to_string(),
            ]
        );
    }

    #[test]
    fn dedupes_by_trimmed_title_keeping_higher_score() {
        let events = sample();
        let got = curated_titles(&events, &[]);
        let disk_count = got.iter().filter(|s| s.as_str() == "ops: Disk Full").count();
        assert_eq!(disk_count, 1);
        assert_eq!(got.first().map(|s| s.as_str()), Some("ops: Disk Full"));
    }

    #[test]
    fn sorts_by_score_then_title_then_id() {
        let events = sample();
        let got = curated_titles(&events, &["feed-z"]);
        assert_eq!(
            got,
            vec![
                "ops: Disk Full".to_string(),
                "ops: Kernel Panic".to_string(),
                "ops: Nightly Backup".to_string(),
            ]
        );
    }

    #[test]
    fn requires_urgent_tag_and_ops_category_only() {
        let events = sample();
        let got = curated_titles(&events, &[]);
        assert!(!got.iter().any(|s| s == "news: Release"));
        assert!(!got.iter().any(|s| s == "ops: Cache Miss"));
        assert!(!got.iter().any(|s| s == "ops: Memory Leak"));
    }
}
