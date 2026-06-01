use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub team: &'static str,
    pub status: &'static str,
    pub hours: u32,
}

pub fn render_report(entries: &[Entry]) -> String {
    let mut per_team: BTreeMap<&str, (u32, u32, u32)> = BTreeMap::new();

    for entry in entries {
        let totals = per_team.entry(entry.team).or_insert((0, 0, 0));
        totals.0 += 1;
        if entry.status == "done" {
            totals.1 += 1;
        }
        totals.2 += entry.hours;
    }

    let mut lines = Vec::new();
    let mut grand_total = 0u32;
    for (team, (tasks, done, hours)) in per_team {
        grand_total += hours;
        lines.push(format!("{team}: tasks={tasks}, done={done}, hours={hours}"));
    }
    lines.push(format!("TOTAL hours={grand_total}"));
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::{render_report, Entry};

    #[test]
    fn groups_sorted_filters_and_totals() {
        let entries = [
            Entry { team: "beta", status: "done", hours: 5 },
            Entry { team: "alpha", status: "wip", hours: 3 },
            Entry { team: "beta", status: "wip", hours: 2 },
            Entry { team: "alpha", status: "done", hours: 4 },
            Entry { team: "alpha", status: "done", hours: 0 },
            Entry { team: "ops", status: "blocked", hours: 0 },
        ];

        let got = render_report(&entries);
        let want = [
            "alpha: tasks=2, done=1, hours=7",
            "beta: tasks=2, done=1, hours=7",
            "TOTAL teams=2, tasks=4, done=2, hours=14",
        ]
        .join("\n");

        assert_eq!(got, want);
    }

    #[test]
    fn empty_after_filter_reports_zero_totals_only() {
        let entries = [
            Entry { team: "ops", status: "blocked", hours: 0 },
            Entry { team: "ops", status: "wip", hours: 0 },
        ];

        assert_eq!(
            render_report(&entries),
            "TOTAL teams=0, tasks=0, done=0, hours=0"
        );
    }
}
