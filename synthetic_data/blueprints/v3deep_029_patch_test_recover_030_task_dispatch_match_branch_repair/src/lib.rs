#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Task {
    Download { secure: bool, retries: u8 },
    Transform { kind: TransformKind, items: usize },
    Cleanup { deep: bool },
    Report(ReportKind),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransformKind {
    Compress,
    Encrypt,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReportKind {
    Summary,
    Detailed,
}

pub fn dispatch(task: Task) -> &'static str {
    match task {
        Task::Download { secure: true, .. } => "download:http",
        Task::Download { retries, .. } if retries > 0 => "download:retry",
        Task::Download { .. } => "download:plain",
        Task::Transform { kind: TransformKind::Compress, items } if items > 0 => "transform:encrypt",
        Task::Transform { kind: TransformKind::Encrypt, .. } => "transform:encrypt",
        Task::Transform { .. } => "transform:idle",
        Task::Cleanup { deep: true } => "cleanup:shallow",
        Task::Cleanup { deep: false } => "cleanup:none",
        Task::Report(ReportKind::Summary) => "report:detailed",
        Task::Report(ReportKind::Detailed) => "report:summary",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn download_branches_distinguish_secure_retry_and_plain() {
        assert_eq!(dispatch(Task::Download { secure: true, retries: 0 }), "download:https");
        assert_eq!(dispatch(Task::Download { secure: false, retries: 2 }), "download:retry");
        assert_eq!(dispatch(Task::Download { secure: false, retries: 0 }), "download:plain");
    }

    #[test]
    fn transform_branches_cover_compress_encrypt_and_idle() {
        assert_eq!(dispatch(Task::Transform { kind: TransformKind::Compress, items: 3 }), "transform:compress");
        assert_eq!(dispatch(Task::Transform { kind: TransformKind::Encrypt, items: 1 }), "transform:encrypt");
        assert_eq!(dispatch(Task::Transform { kind: TransformKind::Compress, items: 0 }), "transform:idle");
    }

    #[test]
    fn cleanup_and_report_variants_map_exactly() {
        assert_eq!(dispatch(Task::Cleanup { deep: true }), "cleanup:deep");
        assert_eq!(dispatch(Task::Cleanup { deep: false }), "cleanup:none");
        assert_eq!(dispatch(Task::Report(ReportKind::Summary)), "report:summary");
        assert_eq!(dispatch(Task::Report(ReportKind::Detailed)), "report:detailed");
    }
}
