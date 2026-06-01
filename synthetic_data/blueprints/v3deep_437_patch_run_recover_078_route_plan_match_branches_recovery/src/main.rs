enum Method {
    Get,
    Post,
    Delete,
    Head,
}

enum Route {
    Users,
    UserById(u32),
    AdminStats,
    Health,
}

struct Request {
    method: Method,
    route: Route,
}

fn method_label(method: &Method) -> &'static str {
    match method {
        Method::Get => "GET",
        Method::Post => "PUT",
        Method::Delete => "DELETE",
        Method::Head => "GET",
    }
}

fn auth_label(req: &Request) -> &'static str {
    match (&req.method, &req.route) {
        (Method::Post, Route::Users) => "token",
        (_, Route::AdminStats) => "token",
        (Method::Delete, Route::UserById(_)) => "admin",
        _ => "public",
    }
}

fn cacheable(req: &Request) -> bool {
    match (&req.method, &req.route) {
        (Method::Get, Route::Users) => true,
        (Method::Head, Route::Health) => false,
        (Method::Get, Route::AdminStats) => true,
        _ => false,
    }
}

fn worker(req: &Request) -> &'static str {
    match (&req.method, &req.route) {
        (_, Route::AdminStats) => "primary",
        (Method::Delete, Route::UserById(_)) => "isolated",
        (Method::Head, Route::Health) => "primary",
        (Method::Get, _) => "edge",
        _ => "primary",
    }
}

fn route_path(route: &Route) -> String {
    match route {
        Route::Users => "/users".to_string(),
        Route::UserById(id) => format!("/users/{id}"),
        Route::AdminStats => "/admin/stats".to_string(),
        Route::Health => "/health".to_string(),
    }
}

fn render(req: &Request) -> String {
    format!(
        "{} {} [{}, cache={}] -> {}",
        method_label(&req.method),
        route_path(&req.route),
        auth_label(req),
        cacheable(req),
        worker(req)
    )
}

fn main() {
    let requests = [
        Request {
            method: Method::Get,
            route: Route::Users,
        },
        Request {
            method: Method::Post,
            route: Route::Users,
        },
        Request {
            method: Method::Delete,
            route: Route::UserById(42),
        },
        Request {
            method: Method::Get,
            route: Route::AdminStats,
        },
        Request {
            method: Method::Head,
            route: Route::Health,
        },
    ];

    for req in requests {
        println!("{}", render(&req));
    }
}
