#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pptagent_runtime.config import node_environment


def register_opencode(source: Path, base: Path) -> Path:
    """Expose only a routing skill, keeping dependency skills out of discovery."""
    target = base / "pptagent"
    marker = target / ".pptagent-source"
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not marker.is_file():
            raise ValueError(f"refusing to replace {target}")
        if marker.read_text().strip() != str(source):
            raise ValueError(f"refusing to replace {target} from another checkout")
    target.mkdir(parents=True, exist_ok=True)
    frontmatter = (source / "SKILL.md").read_text().split("---", 2)[1]
    interpreter = Path(sys.executable).absolute()
    (target / "SKILL.md").write_text(
        f"---{frontmatter}---\n\n# PPTAgent for OpenCode\n\n"
        f"Read and follow the full skill at `{source / 'SKILL.md'}`.\n"
        f"Resolve SKILL_ROOT to `{source}`, not this registration directory.\n"
        f"Use `{interpreter}` as SKILL_PYTHON. References and scripts are in "
        "SKILL_ROOT. The full skill is the source of workflow instructions.\n",
        encoding="utf-8",
    )
    marker.write_text(str(source) + "\n", encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Register this PPTAgent Skill")
    parser.add_argument(
        "--client", choices=("claude", "codex", "opencode"), required=True
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument(
        "--config-home",
        type=Path,
        help="OpenCode config directory (default: <home>/.config/opencode)",
    )
    parser.add_argument("--skip-runtime", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    paths = {
        "claude": ".claude/skills",
        "codex": ".agents/skills",
        "opencode": ".config/opencode/skills",
    }
    if args.config_home and args.client != "opencode":
        parser.error("--config-home applies only to OpenCode")
    base = (
        (
            args.config_home / "skills"
            if args.config_home
            else args.home / paths[args.client]
        )
        .expanduser()
        .resolve()
    )
    target = base / "pptagent"
    if (
        args.client != "opencode"
        and (target.exists() or target.is_symlink())
        and target.resolve() != source
    ):
        parser.exit(2, f"pptagent-install: error: refusing to replace {target}\n")
    if not args.skip_runtime:
        npm = shutil.which("npm")
        if npm is None:
            parser.exit(2, "pptagent-install: error: npm is required\n")
        subprocess.run(
            [npm, "ci", "--prefix", str(source)], check=True, env=node_environment()
        )
    if args.client == "opencode":
        try:
            target = register_opencode(source, base)
        except ValueError as exc:
            parser.exit(2, f"pptagent-install: error: {exc}\n")
    else:
        base.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source, target_is_directory=True)
    print(
        json.dumps(
            {
                "ok": True,
                "client": args.client,
                "skill": str(target),
                "source": str(source),
            }
        )
    )


if __name__ == "__main__":
    main()
