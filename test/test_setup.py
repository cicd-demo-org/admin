import importlib.util
import pathlib
import unittest
from unittest.mock import patch

path = pathlib.Path(__file__).parents[1] / "scripts" / "setup.py"
spec = importlib.util.spec_from_file_location("setup", path)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_ruleset_targets_only_application_and_requires_both_workflows(self):
        result = setup.ruleset("nodejs-demo-app", 123)
        self.assertEqual(result["enforcement"], "active")
        self.assertEqual(result["conditions"]["repository_name"]["include"], ["nodejs-demo-app"])
        workflow_rule = next(rule for rule in result["rules"] if rule["type"] == "workflows")
        self.assertEqual({w["path"] for w in workflow_rule["parameters"]["workflows"]}, {
            ".github/workflows/npm-build-test.yml", ".github/workflows/organization-policy.yml"
        })
        self.assertTrue(all(w["repository_id"] == 123 for w in workflow_rule["parameters"]["workflows"]))
        status_rule = next(rule for rule in result["rules"] if rule["type"] == "required_status_checks")
        self.assertEqual(status_rule["parameters"]["required_status_checks"][0]["context"], "delivery / prod")

    def test_invalid_names_fail_before_any_api_call(self):
        with patch.object(setup, "api") as api:
            with self.assertRaises(ValueError):
                setup.setup("../other", "nodejs-demo-app", "person")
            api.assert_not_called()

    def test_existing_resources_are_updated(self):
        calls = []

        def fake_api(path, method="GET", body=None, paginate=False):
            calls.append((path, method, body))
            if path == "repos/example/required-workflows":
                return {"id": 123}
            if path == "users/person":
                return {"id": 456}
            if path.startswith("orgs/example/teams?"):
                return [[{"slug": setup.TEAM}]]
            if path.startswith("orgs/example/actions/variables?"):
                return [{"variables": [{"name": "DEMO_MODE"}]}]
            if path.startswith("orgs/example/rulesets?"):
                return [[{"name": setup.RULESET_NAME, "id": 789}]]
            return {}

        with patch.object(setup, "api", side_effect=fake_api):
            setup.setup("example", "nodejs-demo-app", "person")
        self.assertIn(("orgs/example/rulesets/789", "PUT", setup.ruleset("nodejs-demo-app", 123)), calls)
        prod = next(body for path, method, body in calls if path.endswith("/environments/prod"))
        self.assertEqual(prod["reviewers"], [{"type": "User", "id": 456}])
        self.assertTrue(any(path.endswith("/DEMO_MODE") and method == "PATCH" for path, method, _ in calls))


if __name__ == "__main__":
    unittest.main()
