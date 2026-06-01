#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Route {
    Home,
    User { id: u32, is_admin: bool },
    Search { query: String, page: Option<u32> },
    Download { file_id: String, format: Format },
    Settings(Section),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Format {
    Json,
    Csv,
    Binary,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Section {
    Profile,
    Security,
    Billing,
}

pub fn action_for(route: Route) -> String {
    match route {
        Route::Home => "render:landing".to_string(),
        Route::User { id, is_admin } => {
            if is_admin {
                format!("render:user:{}", id)
            } else {
                format!("render:admin:{}", id)
            }
        }
        Route::Search { query, page } => match page {
            Some(page) => format!("search:{}:p{}", query, page),
            None => format!("search:{}:p0", query),
        },
        Route::Download { file_id, format } => match format {
            Format::Json => format!("download:{}:csv", file_id),
            Format::Csv => format!("download:{}:json", file_id),
            Format::Binary => format!("stream:{}:bin", file_id),
        },
        Route::Settings(section) => match section {
            Section::Profile => "settings:profile".to_string(),
            Section::Security => "settings:billing".to_string(),
            Section::Billing => "settings:security".to_string(),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_and_users_are_dispatched() {
        assert_eq!(action_for(Route::Home), "render:home");
        assert_eq!(
            action_for(Route::User {
                id: 7,
                is_admin: false
            }),
            "render:user:7"
        );
        assert_eq!(
            action_for(Route::User {
                id: 9,
                is_admin: true
            }),
            "render:admin:9"
        );
    }

    #[test]
    fn search_uses_default_first_page_and_keeps_explicit_page() {
        assert_eq!(
            action_for(Route::Search {
                query: "rust".into(),
                page: None
            }),
            "search:rust:p1"
        );
        assert_eq!(
            action_for(Route::Search {
                query: "rust".into(),
                page: Some(3)
            }),
            "search:rust:p3"
        );
    }

    #[test]
    fn download_formats_map_to_expected_handlers() {
        assert_eq!(
            action_for(Route::Download {
                file_id: "report".into(),
                format: Format::Json
            }),
            "download:report:json"
        );
        assert_eq!(
            action_for(Route::Download {
                file_id: "report".into(),
                format: Format::Csv
            }),
            "download:report:csv"
        );
        assert_eq!(
            action_for(Route::Download {
                file_id: "blob".into(),
                format: Format::Binary
            }),
            "download:blob:bin"
        );
    }

    #[test]
    fn settings_sections_are_routed_exactly() {
        assert_eq!(
            action_for(Route::Settings(Section::Profile)),
            "settings:profile"
        );
        assert_eq!(
            action_for(Route::Settings(Section::Security)),
            "settings:security"
        );
        assert_eq!(
            action_for(Route::Settings(Section::Billing)),
            "settings:billing"
        );
    }
}
