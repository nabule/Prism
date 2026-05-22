from __future__ import annotations

ADMIN_ENTRY_MARKER = "<!-- memosima:admin-entry -->"


def admin_ui_url(public_base_url: str, anchor: str | None = None) -> str:
    base = public_base_url.rstrip("/")
    url = f"{base}/admin/ui"
    if anchor:
        normalized = anchor.removeprefix("#")
        if normalized:
            return f"{url}#{normalized}"
    return url


def build_admin_entry_memo_content(*, public_base_url: str, title: str) -> str:
    admin_url = admin_ui_url(public_base_url)
    jobs_url = admin_ui_url(public_base_url, "jobs")
    candidates_url = admin_ui_url(public_base_url, "tag-candidates")
    summary_url = admin_ui_url(public_base_url, "tag-summary")
    backup_url = admin_ui_url(public_base_url, "backup")
    return (
        f"#系统/Memosima\n\n"
        f"{ADMIN_ENTRY_MARKER}\n\n"
        f"# {title}\n\n"
        f"[打开 Memosima 管理界面]({admin_url})\n\n"
        f"常用操作：\n"
        f"- [查看后台任务]({jobs_url})\n"
        f"- [审核候选标签]({candidates_url})\n"
        f"- [生成标签总结]({summary_url})\n"
        f"- [下载 Sidecar 备份]({backup_url})\n"
    )


def build_summary_admin_links(
    *,
    public_base_url: str,
    has_candidate_tags: bool,
) -> str:
    lines = [
        "### 管理",
        "",
        f"- [打开管理界面]({admin_ui_url(public_base_url)})",
    ]
    if has_candidate_tags:
        lines.append(f"- [审核候选标签]({admin_ui_url(public_base_url, 'tag-candidates')})")
    return "\n".join(lines)
