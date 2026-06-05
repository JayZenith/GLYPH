enum Task {
    Maintenance { hotfix: bool, urgent: bool },
    Build { release: bool, ci: bool },
    Deploy { env: Env, approved: bool },
    Notify { audience: Audience, silent: bool },
}

enum Env {
    Dev,
    Staging,
    Prod,
}

enum Audience {
    Direct,
    Team,
    Broadcast,
}

fn summarize(task: &Task) -> String {
    match task {
        Task::Maintenance { hotfix, urgent } => {
            if *hotfix {
                "maint: hotfix".to_string()
            } else if *urgent {
                "maint: urgent".to_string()
            } else {
                "maint: routine".to_string()
            }
        }
        Task::Build { release, ci } => {
            if *release {
                "build: release".to_string()
            } else if *ci {
                "build: ci".to_string()
            } else {
                "build: local".to_string()
            }
        }
        Task::Deploy { env, approved } => match env {
            Env::Prod => {
                if *approved {
                    "deploy: prod".to_string()
                } else {
                    "deploy: blocked".to_string()
                }
            }
            Env::Staging => "deploy: staging".to_string(),
            Env::Dev => "deploy: dev".to_string(),
        },
        Task::Notify { audience, silent } => match audience {
            Audience::Broadcast => "notify: all".to_string(),
            Audience::Team => {
                if *silent {
                    "notify: team-silent".to_string()
                } else {
                    "notify: team".to_string()
                }
            }
            Audience::Direct => "notify: direct".to_string(),
        },
    }
}

fn main() {
    let cases = vec![
        Task::Maintenance { hotfix: true, urgent: true },
        Task::Maintenance { hotfix: true, urgent: false },
        Task::Build { release: true, ci: true },
        Task::Build { release: false, ci: true },
        Task::Deploy { env: Env::Prod, approved: false },
        Task::Notify { audience: Audience::Team, silent: true },
        Task::Notify { audience: Audience::Broadcast, silent: false },
        Task::Notify { audience: Audience::Direct, silent: true },
    ];

    for task in &cases {
        println!("{}", summarize(task));
    }
}
