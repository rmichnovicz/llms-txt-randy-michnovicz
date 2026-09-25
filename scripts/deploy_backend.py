"""Upload an allowlisted backend bundle with the selected service's config."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["api", "worker", "scheduler"])
    parser.add_argument("--project", default="acadd658-0641-4550-94ae-79a7b934f854")
    parser.add_argument("--environment", default="production")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = root / ("railway.json" if args.service == "api" else f"deploy/railway-{args.service}.json")
    cli = ["npx", "--yes", "@railway/cli"]
    target = ["--project", args.project, "--environment", args.environment]
    status = json.loads(subprocess.check_output([*cli, "status", "--json", *target], cwd=root, text=True))
    service_id = next(s["node"]["id"] for s in status["services"]["edges"] if s["node"]["name"] == args.service)
    settings = json.loads(config.read_text())
    # Apply service settings explicitly: CLI uploads did not honor railway.json
    # in the first deployment. JSON patches also avoid the dot-path CLI no-op.
    patch = {"services": {service_id: {"build": settings["build"], "deploy": settings["deploy"]}}}
    subprocess.run(
        [*cli, "environment", "edit", *target, "--json"],
        input=json.dumps(patch),
        text=True,
        cwd=root,
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="brief-deploy-") as directory:
        bundle = Path(directory)
        for name in ["Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock"]:
            shutil.copy2(root / name, bundle / name)
        shutil.copytree(root / "src", bundle / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(config, bundle / "railway.json")
        subprocess.run(
            [
                "npx",
                "--yes",
                "@railway/cli",
                "up",
                str(bundle),
                "--path-as-root",
                "--project",
                args.project,
                "--environment",
                args.environment,
                "--service",
                args.service,
                "--detach",
            ],
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    main()
