# Swapvera verdict action

Before you merge a model switch, this action tests it on your real production requests and comments the verdict on the pull request: safe to migrate, review these cases, or do not migrate.

The comparison runs on Swapvera with the calls the [Swapvera SDK](https://swapvera.com/docs/#sdk) captured from your app. Generations use the provider key you added in the dashboard; the judge is included. The action installs nothing: it calls the Swapvera API and waits for the result.

```yaml
# .github/workflows/swapvera-verdict.yml
name: Swapvera verdict
on:
  pull_request:
    paths: ['src/llm/**', 'config/models.*']   # where your model IDs live
permissions:
  contents: read
  pull-requests: write
jobs:
  verdict:
    runs-on: ubuntu-latest
    steps:
      - uses: pixelric-spec/swapvera-verdict@v1
        with:
          license: ${{ secrets.SWAPVERA_LICENSE }}
          feature: 'text correction'      # as named in the dashboard; optional with one feature
          to: 'anthropic:claude-haiku-5-5' # or auto: the official replacement when the model is retiring
```

| Input | Default | Meaning |
| --- | --- | --- |
| `license` | | Your project key (`sv_...`), as a secret |
| `feature` | | Feature to test, by its dashboard name. Optional when there is one |
| `to` | `auto` | Replacement model, `provider:model`, or the first suggestion |
| `cases` | `150` | Distinct production requests to compare (10 to 300) |
| `reuse-days` | `7` | Reuse a finished comparison of the same feature and models from the last N days, so re-runs do not spend another comparison |
| `timeout-minutes` | `60` | How long to wait |
| `fail-on` | `do_not_migrate` | `do_not_migrate`, `review` or `never` |
| `comment` | `true` | Post or update one comment on the pull request |

Outputs: `verdict`, `report` and `experiment`. Each new comparison uses one from your plan. The feature needs at least 10 captured calls.
