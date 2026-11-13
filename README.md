# Demo organization setup

`scripts/setup.py` reconciles a narrowly targeted organization ruleset,
`DEMO_MODE=simulation`, three application environments, and the demo reviewer
team. It requires `gh` authenticated as an organization administrator with
`admin:org`, `repo`, and `workflow` scopes. It creates or updates the resources
it names; inspect its effects before running it in any existing organization.

After creating and populating `required-workflows` and `nodejs-demo-app`:

```sh
python3 scripts/setup.py --org cicd-demo-org --repo nodejs-demo-app --approver gclhub
python3 scripts/validate.py --org cicd-demo-org --repo nodejs-demo-app --approver gclhub
python3 -m unittest discover -s test -v
```

The ruleset applies only to the named application and requires the npm and
organization policy workflows and the simulated production check. `prod` has
one required GitHub Environment reviewer; native environment protection does
not enforce two independent role-based approvals. Rulesets require a plan that
supports organization-required workflows. `DEMO_MODE` does not enable any real
integration.

`.github/settings.yml` is an **optional** safe-settings example; no GitHub App
is installed or run by this project. Do not have both tools manage the same
fields without a deliberate ownership policy.
