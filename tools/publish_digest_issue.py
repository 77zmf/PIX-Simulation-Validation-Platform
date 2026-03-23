from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"


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
            {"name": label, "color": "0f7b81", "description": "Automated project digest"},
        )
    except HTTPError as exc:
        if exc.code != 422:
            raise


def find_digest_issue(repo: str, label: str, title: str, token: str) -> dict | None:
    query = quote_plus(f"repo:{repo} is:issue is:open label:{label} in:title")
    payload = api_request("GET", f"/search/issues?q={query}", token)
    for item in payload.get("items", []):
        if item.get("title") == title:
            return item
    return None


def build_issue_body(*, digest_markdown: str, summary: dict, repo: str, label: str) -> str:
    generated_on = summary.get("generated_on", "unknown")
    email = summary.get("email", {})
    email_status = "sent" if email.get("sent") else email.get("reason", "disabled")
    issue_filter = f"https://github.com/{repo}/issues?q=is%3Aissue+is%3Aopen+label%3A{quote_plus(label)}"
    return "\n".join(
        [
            "# Project Digest Inbox",
            "",
            f"- Last updated: `{generated_on}`",
            f"- Email status: `{email_status}`",
            f"- Digest issues filter: [open digest issues]({issue_filter})",
            "",
            "---",
            "",
            digest_markdown,
            "",
        ]
    )


def upsert_issue(repo: str, token: str, title: str, label: str, body: str) -> dict:
    existing = find_digest_issue(repo, label, title, token)
    if existing:
        number = existing["number"]
        return api_request("PATCH", f"/repos/{repo}/issues/{number}", token, {"body": body})
    return api_request("POST", f"/repos/{repo}/issues", token, {"title": title, "body": body, "labels": [label]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update the project digest issue")
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--digest", required=True, help="Path to digest.md")
    parser.add_argument("--summary", required=True, help="Path to digest_summary.json")
    parser.add_argument("--title", default="Project Digest Inbox")
    parser.add_argument("--label", default="project-digest")
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(json.dumps({"published": False, "reason": "missing_token"}))
        return 0

    digest_markdown = Path(args.digest).read_text(encoding="utf-8")
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    ensure_label(args.repo, args.label, token)
    issue = upsert_issue(
        args.repo,
        token,
        title=args.title,
        label=args.label,
        body=build_issue_body(
            digest_markdown=digest_markdown,
            summary=summary,
            repo=args.repo,
            label=args.label,
        ),
    )
    print(json.dumps({"published": True, "issue_url": issue.get("html_url"), "issue_number": issue.get("number")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
