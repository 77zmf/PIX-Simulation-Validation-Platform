from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
DEFAULT_LABEL_COLOR = "1f6feb"


def api_request(method: str, path: str, token: str, payload: dict | None = None) -> dict | list:
    url = f"{API_ROOT}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, method=method, data=data)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def ensure_label(repo: str, label: str, token: str) -> None:
    try:
        api_request(
            "POST",
            f"/repos/{repo}/labels",
            token,
            {
                "name": label,
                "color": DEFAULT_LABEL_COLOR,
                "description": "Plan issue managed from ops/issues",
            },
        )
    except HTTPError as exc:
        if exc.code != 422:
            raise


def find_issue_by_title(repo: str, title: str, token: str) -> dict | None:
    query = quote_plus(f'repo:{repo} is:issue in:title "{title}"')
    payload = api_request("GET", f"/search/issues?q={query}", token)
    for item in payload.get("items", []):
        if item.get("title") == title:
            return item
    return None


def upsert_issue(repo: str, token: str, title: str, labels: list[str], body: str) -> dict:
    existing = find_issue_by_title(repo, title, token)
    if existing:
        number = existing["number"]
        return api_request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            token,
            {"title": title, "body": body, "labels": labels},
        )
    return api_request(
        "POST",
        f"/repos/{repo}/issues",
        token,
        {"title": title, "body": body, "labels": labels},
    )


def mention(username: str | None, fallback: str) -> str:
    if username:
        return f"@{username}"
    return fallback


def render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def build_replacements(args: argparse.Namespace, repo: str) -> dict[str, str]:
    return {
        "PROJECT_NAME": "PIX Simulation Validation Platform",
        "REPO_FULL_NAME": repo,
        "LSX_MENTION": mention(args.lsx_username, "@<lsx_github_username>"),
        "YANG_MENTION": mention(args.yang_username, "@<yang_github_username>"),
        "COORDINATOR_MENTION": mention(args.coordinator_username, "@77zmf"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a repo-side issue plan pack")
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--lsx-username")
    parser.add_argument("--yang-username")
    parser.add_argument("--coordinator-username", default="77zmf")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--render-dir", default="", help="Write rendered issue bodies here")
    return parser.parse_args(argv)


def resolve_body_path(manifest_path: Path, body_path_value: str) -> Path:
    candidate = Path(body_path_value)
    if candidate.is_absolute():
        return candidate
    repo_root = manifest_path.parent.parent.parent.parent
    return repo_root / candidate


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacements = build_replacements(args, args.repo)

    if not args.dry_run and (not args.lsx_username or not args.yang_username):
        print(json.dumps({"published": False, "reason": "missing_required_usernames"}))
        return 0

    if not args.dry_run and not token:
        print(json.dumps({"published": False, "reason": "missing_token"}))
        return 0

    render_dir = Path(args.render_dir).resolve() if args.render_dir else None
    if render_dir:
        render_dir.mkdir(parents=True, exist_ok=True)

    published: list[dict[str, object]] = []
    rendered: list[dict[str, object]] = []

    for item in manifest.get("issues", []):
        body_path = resolve_body_path(manifest_path, item["body_path"])
        template = body_path.read_text(encoding="utf-8")
        body = render_template(template, replacements)
        title = item["title"]
        labels = item.get("labels", [])

        rendered.append({"title": title, "labels": labels, "body_path": str(body_path)})

        if render_dir:
            slug = item.get("slug", title.lower().replace(" ", "_"))
            (render_dir / f"{slug}.md").write_text(body, encoding="utf-8")

        if args.dry_run:
            continue

        for label in labels:
            ensure_label(args.repo, label, token)
        issue = upsert_issue(args.repo, token, title=title, labels=labels, body=body)
        published.append(
            {
                "title": title,
                "issue_number": issue.get("number"),
                "issue_url": issue.get("html_url"),
            }
        )

    print(
        json.dumps(
            {
                "published": not args.dry_run,
                "render_dir": str(render_dir) if render_dir else None,
                "rendered_count": len(rendered),
                "issues": published if not args.dry_run else rendered,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
