# OpenCode integration

Complete the [source installation](../README.md#quick-start), then register:

```bash
.venv/bin/python scripts/install.py --client opencode
opencode debug skill
```

The installer creates a small routing skill at
`~/.config/opencode/skills/pptagent/SKILL.md`, pointing to this checkout and its
interpreter. Keep both in place; rerun registration after moving either.
Existing unmanaged registrations are not overwritten. `--config-home` selects
an alternative OpenCode configuration directory.

OpenCode also discovers Claude/Agents skill directories. If discovery shows
an old duplicate registration, remove that registration rather than the source
skill. Restart OpenCode after configuration changes.

## Visual MCP

For a text-only host, set `mode: text` and configure the visual model in the
skill's `config.yaml`, with `VISUAL_API_KEY` in its ignored `.env`. See
[visual configuration](../README.md#visual-review) and the
[Duanyan example](../examples/duanyan.yaml). Your OpenCode authoring model remains
independent of the visual reviewer.

Initialize a separate task directory from `skills/pptagent/`:

```bash
.venv/bin/python scripts/pptagent.py init --workspace ~/pptagent-demo --slides 3
```

Merge this into the task's `opencode.json`, replacing every absolute path:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "pptagent-visual": {
      "type": "local",
      "command": [
        "/absolute/path/to/PPTAgent/skills/pptagent/.venv/bin/python",
        "/absolute/path/to/PPTAgent/skills/pptagent/scripts/visual_mcp.py",
        "--workspace", "/absolute/path/to/pptagent-demo"
      ],
      "enabled": true,
      "timeout": 1800000
    }
  }
}
```

This is a workspace-bound stdio adapter, separate from the legacy
`pptagent-mcp` template generator. No network listener is needed. Optional
`--config` and `--env` arguments select alternative configuration files.

Start OpenCode in that task directory and check `opencode mcp list`. Ask it to
use the installed `pptagent` skill and the `pptagent-visual` tools:

1. Author the requested HTML slides.
2. Call `review_slides`; fix major visible issues.
3. Run the skill CLI's `build`.
4. Call `review_deck` to inspect the exported PPTX.
5. Run `finalize`; deliver when `complete=true`.

Use normal project configuration for `opencode run --dir /absolute/task/path`;
`run --pure` can omit the task-local MCP. Successful tool discovery alone does
not prove the model has called the tools or completed the workflow.

A tool response with `ok: false` is a failed visual review, not a transport
failure. Do not replace it with a manual pass. Passing reviews can be reused
only when sources, resources, rendered images, endpoint/model and review prompts
match. Failed, stale, unsigned older and manual records are reviewed again.
Results mark reused pages with `reused: true`; `review_slides(force=true)` forces
fresh review. Exported-deck review always makes a fresh call.

## Research services

Put the desired search key and `MINERU_API_KEY` in the skill's `.env` with
permissions `0600`. The launcher loads it in the MCP process; keep research keys
out of the host's launch environment, prompts and task configuration. Existing
environment values take precedence. Do not print the effective environment.

Add either or both servers to the task's `mcp` object:

```json
{
  "pptagent-search": {
    "type": "local",
    "command": [
      "/absolute/path/to/PPTAgent/skills/pptagent/.venv/bin/python",
      "/absolute/path/to/PPTAgent/skills/pptagent/scripts/research_mcp.py",
      "search", "--workspace", "/absolute/path/to/pptagent-demo"
    ],
    "enabled": true,
    "timeout": 120000
  },
  "pptagent-docs": {
    "type": "local",
    "command": [
      "/absolute/path/to/PPTAgent/skills/pptagent/.venv/bin/python",
      "/absolute/path/to/PPTAgent/skills/pptagent/scripts/research_mcp.py",
      "documents", "--workspace", "/absolute/path/to/pptagent-demo"
    ],
    "enabled": true,
    "timeout": 1800000
  }
}
```

The editable source installation provides the updated package; no `PYTHONPATH`
override is needed. Search exposes `search_web`, `search_images`, `fetch_url`
and `download_file`; documents exposes `convert_to_markdown`.

For an already downloaded public PDF, pass its local `file_path`, an empty
`output_folder`, and optionally `source_url` for the same HTTPS PDF. MinerU can
fetch that URL instead of using local upload. This still uses the authenticated
MinerU parser; retain the PDF and extracted artifacts for source verification.

The clients honor proxy environment settings. Where explicit forwarding is
needed, use environment references such as `"HTTPS_PROXY": "{env:HTTPS_PROXY}"`
in the server's `environment`. Enable only the services needed for the task.

Official configuration references: [OpenCode skills](https://opencode.ai/docs/skills/)
and [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/).
