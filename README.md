# Swapvera verdict action

Comments a verdict on every pull request that changes your model or prompts: safe to migrate, review these cases, or do not migrate.

```yaml
# .github/workflows/swapvera-verdict.yml
name: Swapvera verdict
on:
  pull_request:
    paths: ['swapvera.yaml', 'cases.jsonl', 'prompts/**', 'src/llm/**']
permissions:
  contents: read
  pull-requests: write
jobs:
  verdict:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pixelric-spec/swapvera-verdict@v1
        with:
          license: ${{ secrets.SWAPVERA_LICENSE }}
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}   # your keys: the models run from your runner
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Outputs: `verdict` and `report`. With `fail-on: review` the job also fails when some cases need review.

`share: true` adds your anonymous outcome categories to the [migration atlas](https://swapvera.example/atlas/) (output formats, check types, which ones got worse; never prompts or outputs). It needs a license, and a failed upload never fails the job.
