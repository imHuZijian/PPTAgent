# PPTAgent Skill

Create editable PowerPoint presentations with Claude Code, Codex, or OpenCode.
Your host agent researches and authors HTML slides; the skill renders, reviews,
exports, and verifies the resulting PPTX. Supported layouts: 16:9, 4:3, and A1.

## Quick start

Requirements: Linux/WSL or macOS, Python 3.11+, [uv](https://docs.astral.sh/uv/),
Node.js/npm, and LibreOffice on PATH as `libreoffice` or `soffice`.
On macOS the converter also uses Google Chrome. On Debian/Ubuntu, install
`npm` and `libreoffice-impress`; on macOS, Homebrew's LibreOffice cask provides
`soffice`.

From this repository's `skills/pptagent/` directory:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ../.. -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium

# Choose claude, codex, or opencode.
.venv/bin/python scripts/install.py --client opencode
.venv/bin/python scripts/pptagent.py doctor
```

The editable install uses the Python package and converter from this checkout,
including the search and document tools. No `PYTHONPATH` override is required.
Keep the full checkout and `.venv` in place. The installer uses `npm ci` with
the skill's lockfile; `--skip-runtime` is only for an already prepared runtime.

| Client | Registration |
| --- | --- |
| Claude Code | `~/.claude/skills/pptagent` |
| Codex | `~/.agents/skills/pptagent` |
| OpenCode | `~/.config/opencode/skills/pptagent` (lightweight routing entry) |

Restart the client after installation. Use your existing authoring model and
start in a separate task directory. For OpenCode's external visual MCP and
optional research tools, follow the [OpenCode guide](references/opencode.md).

## Try it

```text
Use the pptagent skill to create a 6-slide, 16:9 presentation for a project
review. Use the documents in this folder as sources. Include an editable
comparison table and workflow diagram, and cite external claims.
Review the slides and exported deck, fix visible issues, and deliver
answer.pptx only when finalize reports complete=true.
```

Ask for revisions in the same task directory. It retains `answer.pptx`, HTML
sources, assets, previews, and `final-report.json`. Text and tables remain
editable; source images and some visual effects are raster assets.

## Configuration

The host's authoring model is configured in the host itself. The skill's
configuration controls visual review and delivery, not the authoring model.

### Visual review

- `mode: multimodal` (default): the host must actually be able to inspect images.
- `mode: text`: a separate image-capable model reviews renders through an
  OpenAI-compatible Chat Completions endpoint.

For first-time setup, copy `config.example.yaml` to `config.yaml` and
`.env.example` to `.env`; preserve existing files if already configured.
Run `chmod 600 .env` and keep credentials out of task folders and Git.

Example text-mode configuration:

```yaml
mode: text
visual:
  base_url: https://your-provider.example/v1
  model: your-vision-model
  api_key_env: VISUAL_API_KEY
  timeout_seconds: 300
delivery:
  mode: strict
```

Set `VISUAL_API_KEY` in the skill's ignored `.env`. Environment variables take
precedence. The client appends `/chat/completions` to `base_url`. A
[Duanyan example](examples/duanyan.yaml) is included; confirm the endpoint and
model availability in your account. `doctor` checks local requirements and
configuration, not API connectivity.

Review covers visible layout and readability; the host must verify facts and
citations. Transient connection errors and HTTP 502/503/504 receive at most two
retries. Authentication, quota and malformed-response errors are not retried.
Unchanged passing slide reviews from the same reviewer can be reused;
`review-slides --force` requests a fresh inspection. Failed or stale reviews
never establish acceptance. See the [text-mode contract](references/text.md).

### Optional research tools

Use the host's existing research tools or connect the skill's research launcher
as described in the [OpenCode guide](references/opencode.md#research-services).
It reads the skill's `.env` inside the MCP process; research keys do not need
to be exported to the author process.

| Service | Setting | Purpose |
| --- | --- | --- |
| Serper | `SERPER_API_KEY` | Web and image search |
| SerpAPI | `SERPAPI_KEY` | Alternative Google search backend |
| Tavily | `TAVILY_API_KEY` | Alternative research search backend |
| MinerU | `MINERU_API_KEY` | Hosted PDF parsing into Markdown, tables and figures |
| Local PDF service | `MINERU_API_URL` | Compatible multipart-PDF endpoint returning a ZIP |

Search precedence is SerpAPI, Serper, then Tavily. Without a search key, URL
fetching and downloading remain available. For PDFs, the hosted MinerU key
takes precedence over the local endpoint; without either, conversion uses
MarkItDown. Public PDFs can be submitted to MinerU through `source_url` when
the same PDF has been saved locally. Keep source PDFs and figure references
in the task workspace. Account or mailbox passwords are not required.

## Delivery and maintenance

Strict delivery requires current slide reviews, a matching build, and an
exported-deck review. Only use `delivery.mode: best-effort` when the user accepts
an incomplete draft, and disclose the remaining failed checks.

For maintainers, run the regression suite from `skills/pptagent/`:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary workspaces and mock API responses, not paid model calls.
Browser/export tests need the installed runtime; the LibreOffice round trip
runs when LibreOffice is available.

- [Skill instructions](SKILL.md)
- [HTML and workspace contract](references/task-contract.md)
- [OpenCode integration](references/opencode.md)
- [Project home](../../README.md)

The skill is distributed in this Git repository. The Python wheel contains the
`pptagent` and `deeppresenter` packages, not this skill directory; installing
only the PyPI package does not register a host skill.
