"""Build/deploy an isolated, immutable-capture replay. Never modifies Brief."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urljoin

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demos/wayback"
PROJECT = "brief-history-demo"


def build(version: str) -> Path:
    metadata = json.loads((DATA / "manifest.json").read_text())[version]
    raw = (DATA / metadata["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("Archive capture checksum mismatch")
    tree = html.fromstring(raw)
    for node in tree.xpath("//script|//iframe|//object|//embed|//base|//form|//link|//meta[@http-equiv]"):
        node.drop_tree()
    for node in tree.iter():
        for key in list(node.attrib):
            if key.lower().startswith("on"):
                del node.attrib[key]
        if node.get("href"):
            node.set("href", urljoin(metadata["original_url"], node.get("href")))
    # Visible provenance outside the source's main content. The captured prose is untouched.
    banner = html.fragment_fromstring(
        '<aside style="padding:12px;background:#fff;color:#222;font:14px system-ui">Historical replay of HTML5 Boilerplate · '
        + metadata["timestamp"]
        + ' · independent demo. <a href="/provenance.json">Provenance</a></aside>'
    )
    body = tree.find("body")
    if body is None:
        raise ValueError("Archive capture has no body element")
    body.insert(0, banner)
    rendered = html.tostring(tree, encoding="unicode", method="html")
    metadata = {
        **metadata,
        "version": version,
        "scope": "One captured homepage, not a complete historical website",
        "transformations": "Scripts/forms/embedded frames/external stylesheets removed; links resolved against original URL; provenance banner added. Missing resources return 503.",
        "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
    }
    out = ROOT / "evals/results/wayback-demo" / version
    out.mkdir(parents=True, exist_ok=True)
    (out / "_worker.js").write_text(
        "const SNAPSHOT = "
        + json.dumps({"metadata": metadata, "html": rendered})
        + ";\n"
        + (DATA / "worker.js").read_text()
    )
    (out / "index.html").write_text("Historical replay; content served by the worker.")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", choices=["before", "after"])
    parser.add_argument("--deploy", action="store_true")
    args = parser.parse_args()
    out = build(args.version)
    print(out)
    if args.deploy:
        subprocess.run(
            [
                str(ROOT / "frontend/node_modules/.bin/wrangler"),
                "pages",
                "deploy",
                str(out),
                "--project-name",
                PROJECT,
                "--branch",
                "main",
                "--commit-dirty=true",
                "--force",
            ],
            cwd=out,
            check=True,
        )
        print(f"https://{PROJECT}.pages.dev/site/")


if __name__ == "__main__":
    main()
