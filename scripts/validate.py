#!/usr/bin/env python3
"""Verify the provisioned demo baseline without changing it."""

import argparse
import sys

from setup import RULESET_NAME, TEAM, api, pages, ruleset


def validate(org, repo, approver):
    repo_info = api(f"repos/{org}/{repo}")
    if repo_info["private"]:
        raise ValueError("The application repository must be public.")
    workflow_id = api(f"repos/{org}/required-workflows")["id"]
    reviewer_id = api(f"users/{approver}")["id"]
    variable = api(f"orgs/{org}/actions/variables/DEMO_MODE")
    if variable["value"] != "simulation" or variable["visibility"] != "all":
        raise ValueError("DEMO_MODE must be simulation and visible to all repositories.")
    if not any(item["slug"] == TEAM for item in pages(f"orgs/{org}/teams?per_page=100")):
        raise ValueError("The demo reviewer team is missing.")
    for name in ("dev", "test", "prod"):
        environment = api(f"repos/{org}/{repo}/environments/{name}")
        if name == "prod":
            rules = environment.get("protection_rules", [])
            if not any(rule.get("type") == "required_reviewers"
                       and any(reviewer.get("type") == "User"
                               and reviewer.get("reviewer", {}).get("id") == reviewer_id
                               for reviewer in rule.get("reviewers", []))
                       for rule in rules):
                raise ValueError("Production does not require the configured reviewer.")
    matches = [item for item in pages(f"orgs/{org}/rulesets?per_page=100")
               if item["name"] == RULESET_NAME]
    if len(matches) != 1:
        raise ValueError("Expected exactly one demo ruleset.")
    actual = api(f"orgs/{org}/rulesets/{matches[0]['id']}")
    expected = ruleset(repo, workflow_id)
    if actual["enforcement"] != "active":
        raise ValueError("Demo ruleset is not active.")
    if actual["conditions"]["repository_name"] != expected["conditions"]["repository_name"]:
        raise ValueError("Demo ruleset repository targeting differs from the baseline.")
    actual_rules = {item["type"]: item for item in actual["rules"]}
    for rule in expected["rules"]:
        if rule["type"] not in actual_rules:
            raise ValueError(f"Missing ruleset rule: {rule['type']}")
    required = actual_rules["workflows"]["parameters"]["workflows"]
    if {(w["repository_id"], w["ref"], w["path"]) for w in required} != {
        (workflow_id, "refs/heads/main", ".github/workflows/npm-build-test.yml"),
        (workflow_id, "refs/heads/main", ".github/workflows/organization-policy.yml"),
    }:
        raise ValueError("Required workflows differ from the baseline.")
    contexts = actual_rules["required_status_checks"]["parameters"]["required_status_checks"]
    if not any(item["context"] == "delivery / prod" for item in contexts):
        raise ValueError("Simulated production is not a required check.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    parser.add_argument("--repo", default="nodejs-demo-app")
    parser.add_argument("--approver", required=True)
    args = parser.parse_args()
    try:
        validate(args.org, args.repo, args.approver)
    except (RuntimeError, ValueError, KeyError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    print("Demo baseline validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
