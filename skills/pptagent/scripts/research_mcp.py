#!/usr/bin/env python3
"""Start the package research servers with the skill's local environment."""

from __future__ import annotations

import argparse
import os
import runpy
from pathlib import Path

from pptagent_runtime.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("search", "documents"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--env", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error("workspace must be an existing directory")
    load_config(env_path=args.env)
    os.environ["WORKSPACE"] = str(workspace)
    module = "search" if args.service == "search" else "any2markdown"
    runpy.run_module(f"deeppresenter.tools.{module}", run_name="__main__")


if __name__ == "__main__":
    main()
