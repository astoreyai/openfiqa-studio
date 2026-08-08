"""openfiqa-studio — command line interface (P06 W13).

ADR-0009: the GUI and this CLI execute the same serialised workflow through the same compiler and
executor. There is no separate CLI code path, so "run it from the CLI" is a test of the product
rather than a porting exercise.

    openfiqa-studio validate workflow.yaml
    openfiqa-studio run workflow.yaml [--workdir DIR] [--manifest OUT]
    openfiqa-studio compile workflow.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_workflow.executor import WorkflowExecutor, workflow_digest  # noqa: E402
from studio_workflow.graph import Workflow, WorkflowError, compile_workflow  # noqa: E402


def cmd_validate(args: argparse.Namespace) -> int:
    workflow = Workflow.read(args.workflow)
    problems = workflow.validate()
    if problems:
        print(f"✗ {workflow.name}: {len(problems)} problem(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"✓ {workflow.name} is valid ({len(workflow.nodes)} nodes, {len(workflow.edges)} edges)")
    print(f"  workflow sha256: {workflow_digest(workflow)}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    workflow = Workflow.read(args.workflow)
    try:
        plan = compile_workflow(workflow)
    except WorkflowError as exc:
        print(f"✗ {exc}")
        return 1
    print(json.dumps([n.to_dict() for n in plan], indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    workflow = Workflow.read(args.workflow)
    try:
        workflow.require_valid()
    except WorkflowError as exc:
        print(f"✗ {exc}")
        return 1

    executor = WorkflowExecutor(Path(args.workdir))
    manifest = executor.run(workflow, limit_samples=args.limit)

    for node in manifest.nodes:
        mark = {"completed": "✓", "blocked": "■", "failed": "✗"}[node.status]
        blocker = f" [{node.blocker_id}]" if node.blocker_id else ""
        print(f" {mark} {node.node_id:36} {node.status:9}{blocker} {node.detail or ''}")

    print(f"\nstatus: {manifest.status}")
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(manifest.to_dict(), indent=2))
        print(f"manifest: {args.manifest}")

    # A partial run exits 0: blocked stages are a documented state, not a failure of the run.
    # A failed node is a real failure and exits non-zero.
    return 1 if manifest.status == "failed" else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openfiqa-studio", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="type-check a workflow without running it")
    validate.add_argument("workflow")
    validate.set_defaults(func=cmd_validate)

    compile_ = sub.add_parser("compile", help="show the expanded execution plan")
    compile_.add_argument("workflow")
    compile_.set_defaults(func=cmd_compile)

    run = sub.add_parser("run", help="execute a workflow")
    run.add_argument("workflow")
    run.add_argument("--workdir", default="var/runs")
    run.add_argument("--manifest", default=None, help="write the run manifest here")
    run.add_argument("--limit", type=int, default=None, help="cap samples per dataset node")
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
