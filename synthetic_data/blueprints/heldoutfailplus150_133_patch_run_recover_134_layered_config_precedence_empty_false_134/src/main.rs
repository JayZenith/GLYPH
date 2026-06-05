use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Layer {
    host: Option<String>,
    port: Option<u16>,
    mode: Option<String>,
    debug: Option<bool>,
    color: Option<bool>,
    labels: Option<Vec<String>>,
}

#[derive(Clone, Debug)]
struct Resolved {
    host: String,
    host_src: &'static str,
    port: u16,
    port_src: &'static str,
    mode: String,
    mode_src: &'static str,
    debug: bool,
    debug_src: &'static str,
    color: bool,
    color_src: &'static str,
    labels: Vec<String>,
    labels_src: &'static str,
}

fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "1" | "yes" | "on" => Some(true),
        "false" | "0" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn parse_labels_csv(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .map(|p| p.to_string())
        .collect()
}

fn parse_layer(map: &HashMap<&str, &str>) -> Layer {
    Layer {
        host: map.get("host").and_then(|v| if v.is_empty() { None } else { Some((*v).to_string()) }),
        port: map.get("port").and_then(|v| v.parse::<u16>().ok()),
        mode: map.get("mode").and_then(|v| if v.is_empty() { None } else { Some((*v).to_string()) }),
        debug: map.get("debug").and_then(|v| if *v == "false" { None } else { parse_bool(v) }),
        color: map.get("color").and_then(|v| if *v == "false" { None } else { parse_bool(v) }),
        labels: map.get("labels").and_then(|v| {
            let parsed = parse_labels_csv(v);
            if parsed.is_empty() { None } else { Some(parsed) }
        }),
    }
}

fn merge(defaults: Layer, file: Layer, env: Layer, cli: Layer) -> Resolved {
    let mut out = Resolved {
        host: defaults.host.unwrap_or_else(|| "localhost".to_string()),
        host_src: "default",
        port: defaults.port.unwrap_or(8080),
        port_src: "default",
        mode: defaults.mode.unwrap_or_else(|| "prod".to_string()),
        mode_src: "default",
        debug: defaults.debug.unwrap_or(false),
        debug_src: "default",
        color: defaults.color.unwrap_or(true),
        color_src: "default",
        labels: defaults.labels.unwrap_or_else(Vec::new),
        labels_src: "default",
    };

    for (layer, name) in [(&file, "file"), (&env, "env"), (&cli, "cli")] {
        if let Some(v) = &layer.host {
            if !v.is_empty() {
                out.host = v.clone();
                out.host_src = name;
            }
        }
        if let Some(v) = layer.port {
            out.port = v;
            out.port_src = name;
        }
        if let Some(v) = &layer.mode {
            if !v.is_empty() {
                out.mode = v.clone();
                out.mode_src = name;
            }
        }
        if layer.debug == Some(true) {
            out.debug = true;
            out.debug_src = name;
        }
        if layer.color == Some(true) {
            out.color = true;
            out.color_src = name;
        }
        if let Some(v) = &layer.labels {
            if !v.is_empty() {
                out.labels = v.clone();
                out.labels_src = name;
            }
        }
    }

    out
}

fn main() {
    let defaults = Layer {
        host: Some("localhost".to_string()),
        port: Some(8080),
        mode: Some("prod".to_string()),
        debug: Some(true),
        color: Some(true),
        labels: Some(vec!["base".to_string()]),
    };

    let file_map = HashMap::from([
        ("host", "file.internal"),
        ("port", "9000"),
        ("mode", "dev"),
        ("debug", "true"),
        ("color", "true"),
        ("labels", "api,blue"),
    ]);
    let env_map = HashMap::from([
        ("host", "env.internal"),
        ("port", "7000"),
        ("labels", ""),
    ]);
    let cli_map = HashMap::from([
        ("host", ""),
        ("debug", "false"),
        ("color", "false"),
    ]);

    let resolved = merge(
        defaults,
        parse_layer(&file_map),
        parse_layer(&env_map),
        parse_layer(&cli_map),
    );

    println!("host={}", resolved.host);
    println!("port={}", resolved.port);
    println!("mode={}", resolved.mode);
    println!("debug={}", resolved.debug);
    println!("color={}", resolved.color);
    println!("labels=[{}]", resolved.labels.join(","));
    println!("source_host={}", resolved.host_src);
    println!("source_port={}", resolved.port_src);
    println!("source_mode={}", resolved.mode_src);
    println!("source_debug={}", resolved.debug_src);
    println!("source_color={}", resolved.color_src);
    print!("source_labels={}", resolved.labels_src);
}
