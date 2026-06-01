use std::cmp::Ordering;

#[derive(Clone)]
struct Team {
    name: &'static str,
    points: u32,
    goals_for: i32,
    goals_against: i32,
}

impl Team {
    fn goal_diff(&self) -> i32 {
        self.goals_for - self.goals_against
    }
}

fn better(a: &Team, b: &Team) -> bool {
    a.points > b.points
}

fn dedupe_best(teams: Vec<Team>) -> Vec<Team> {
    let mut out: Vec<Team> = Vec::new();
    for team in teams {
        if let Some(existing) = out.iter_mut().find(|t| t.name == team.name) {
            if existing.points > team.points {
                *existing = team;
            }
        } else {
            out.push(team);
        }
    }
    out
}

fn rank_table(mut teams: Vec<Team>) -> Vec<Team> {
    teams.sort_by(|a, b| {
        a.points
            .cmp(&b.points)
            .then_with(|| a.goal_diff().cmp(&b.goal_diff()))
            .then_with(|| a.goals_for.cmp(&b.goals_for))
            .then_with(|| b.name.cmp(&a.name))
    });
    teams
}

fn render(teams: &[Team]) -> String {
    let mut lines = Vec::new();
    for (i, t) in teams.iter().enumerate() {
        lines.push(format!(
            "{}. {} - {} pts, {:+} gd, {} gf",
            i + 1,
            t.name,
            t.points,
            t.goal_diff(),
            t.goals_for
        ));
    }
    lines.join("\n")
}

fn main() {
    let teams = vec![
        Team { name: "Lions", points: 10, goals_for: 9, goals_against: 4 },
        Team { name: "Bears", points: 10, goals_for: 8, goals_against: 3 },
        Team { name: "Wolves", points: 8, goals_for: 7, goals_against: 4 },
        Team { name: "Tigers", points: 10, goals_for: 9, goals_against: 4 },
        Team { name: "Hawks", points: 10, goals_for: 10, goals_against: 6 },
        Team { name: "Wolves", points: 8, goals_for: 6, goals_against: 4 },
    ];

    let teams = dedupe_best(teams);
    let ranked = rank_table(teams);
    println!("{}", render(&ranked));
}
