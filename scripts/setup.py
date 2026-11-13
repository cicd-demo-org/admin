#!/usr/bin/env python3
"""Reconcile the explicitly named demo resources in an existing organization."""

import argparse
import json
import subprocess
import sys

RULESET_NAME = "Node demo required workflows"
TEAM = "demo-release-reviewers"


def api(path, method="GET", body=None, paginate=False):
    command = ["gh", "api", "--method", method, path]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    if body is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(
        command, input=None if body is None else json.dumps(body),
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"GitHub API {method} {path} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path):
    return [entry for page in api(path, paginate=True) for entry in page]


def ruleset(repo_name, workflows_id):
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "repository_name": {"include": [repo_name], "exclude": []},
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []},
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": False,
                "required_review_thread_resolution": True,
                "require_last_push_approval": False,
            }},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "delivery / prod"}],
            }},
            {"type": "workflows", "parameters": {
                "do_not_enforce_on_create": True,
                "workflows": [
                    {"repository_id": workflows_id, "ref": "refs/heads/main",
                     "path": ".github/workflows/npm-build-test.yml"},
                    {"repository_id": workflows_id, "ref": "refs/heads/main",
                     "path": ".github/workflows/organization-policy.yml"},
                ],
            }},
        ],
    }


def setup(org, repo, approver):
    if not all(value and value.replace("-", "").replace("_", "").isalnum()
               for value in (org, repo, approver)):
        raise ValueError("Organization, repository and approver must be simple GitHub names.")
    api(f"repos/{org}/{repo}")
    workflows_id = api(f"repos/{org}/required-workflows")["id"]
    reviewer_id = api(f"users/{approver}")["id"]

    teams = pages(f"orgs/{org}/teams?per_page=100")
    if not any(team["slug"] == TEAM for team in teams):
        api(f"orgs/{org}/teams", "POST", {"name": TEAM, "privacy": "closed"})
    api(f"orgs/{org}/teams/{TEAM}/memberships/{approver}", "PUT", {"role": "member"})

    variable_pages = api(f"orgs/{org}/actions/variables?per_page=100", paginate=True)
    variables = [item for page in variable_pages for item in page["variables"]]
    variable = {"name": "DEMO_MODE", "value": "simulation", "visibility": "all"}
    if any(item["name"] == "DEMO_MODE" for item in variables):
        api(f"orgs/{org}/actions/variables/DEMO_MODE", "PATCH", variable)
    else:
        api(f"orgs/{org}/actions/variables", "POST", variable)

    for environment in ("dev", "test", "prod"):
        config = {"wait_timer": 0, "prevent_self_review": False}
        if environment == "prod":
            config["reviewers"] = [{"type": "User", "id": reviewer_id}]
        else:
            config["reviewers"] = []
        api(f"repos/{org}/{repo}/environments/{environment}", "PUT", config)

    existing = [item for item in pages(f"orgs/{org}/rulesets?per_page=100")
                if item["name"] == RULESET_NAME]
    if len(existing) > 1:
        raise RuntimeError(f"Multiple rulesets named {RULESET_NAME!r}; resolve them manually.")
    body = ruleset(repo, workflows_id)
    if existing:
        api(f"orgs/{org}/rulesets/{existing[0]['id']}", "PUT", body)
    else:
        api(f"orgs/{org}/rulesets", "POST", body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    parser.add_argument("--repo", default="nodejs-demo-app")
    parser.add_argument("--approver", required=True)
    args = parser.parse_args()
    try:
        setup(args.org, args.repo, args.approver)
    except (RuntimeError, ValueError, KeyError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    print("Demo configuration applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
