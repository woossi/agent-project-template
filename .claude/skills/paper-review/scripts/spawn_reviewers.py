"""Spawn N peer reviewer subprocesses via claude -p in parallel.

Each reviewer is its own `claude -p` subprocess running concurrently. This
sidesteps the headless Claude Code host's tendency to serialize Agent tool
calls (one tool_use per turn), which we observed adding ~3 minutes of
unnecessary wall-clock time per reviewer in production runs.

Reviewers retain full tool access (Bash for arxiv_search, etc.) since each
child is a real Claude Code instance.
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from pathlib import Path


NATO = ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]


def build_prompt(template: Path, *, reviewer_id: str, paper_text: str, skill_dir: str, domain: str) -> str:
    text = template.read_text()
    return (
        text.replace("{reviewer_id}", reviewer_id)
        .replace("{skill_dir}", skill_dir)
        .replace("{domain}", domain)
        .replace("{paper_text}", paper_text)
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Spawn parallel peer reviewers via claude -p.")
    p.add_argument("--paper-text-file", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--skill-dir", required=True)
    p.add_argument("--num-reviewers", type=int, default=3)
    p.add_argument("--alignment-critic", dest="alignment_critic", action="store_true", default=True)
    p.add_argument("--no-alignment-critic", dest="alignment_critic", action="store_false")
    p.add_argument("--domain", default="this paper's domain (inferred from text)")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--overwrite", action="store_true")
    # SAFETY (team-umc fork): reviewer children run under a gated allow-list,
    # NOT --dangerously-skip-permissions. They only need to read files and run
    # the bundled arxiv_search.py. Override with --allowed-tools if a paper
    # genuinely needs more, but never re-introduce a blanket permission bypass.
    p.add_argument(
        "--allowed-tools",
        dest="allowed_tools",
        default="Read,Grep,Glob,Bash(python3 *),Bash(python *)",
        help="Comma/space-separated allow-list passed to each reviewer's claude -p (default: read + arxiv_search only).",
    )
    args = p.parse_args()

    n = max(3, min(8, args.num_reviewers))
    codenames = NATO[:n]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = str(Path(args.skill_dir).resolve())
    paper_text = Path(args.paper_text_file).read_text()

    standard_template = Path(skill_dir) / "prompts" / "reviewer.md"
    af_template = Path(skill_dir) / "prompts" / "reviewer_alignment_forum.md"

    af_idx = random.randrange(n) if args.alignment_critic else -1

    procs: list[tuple[str, subprocess.Popen | None, object, Path | None]] = []
    start = time.time()
    spawn_count = 0
    for i, code in enumerate(codenames):
        out_path = output_dir / f"review_{code}.md"
        if out_path.exists() and not args.overwrite:
            print(f"[spawn_reviewers] skip {code} (exists, --overwrite not set)", file=sys.stderr, flush=True)
            procs.append((code, None, None, None))
            continue
        # Stagger spawns by 10 s so concurrent reviewers don't all hit arXiv
        # in the same instant and trigger 429 cascades. Trades a small amount
        # of wall-clock for much higher reliability per reviewer.
        if spawn_count > 0:
            time.sleep(10)
        spawn_count += 1
        template = af_template if i == af_idx else standard_template
        prompt = build_prompt(
            template,
            reviewer_id=code,
            paper_text=paper_text,
            skill_dir=skill_dir,
            domain=args.domain,
        )
        out_fh = open(out_path, "w")
        # SAFETY (team-umc fork): no --dangerously-skip-permissions. Each
        # reviewer child runs under an explicit allow-list and is confined to
        # the output dir via --add-dir, so it cannot touch the manuscript tree
        # or run arbitrary tools without a gate. The review itself is written
        # via stdout redirection (out_fh), so Write access is not granted.
        proc = subprocess.Popen(
            [
                "claude",
                "--allowedTools", args.allowed_tools,
                "--add-dir", str(output_dir.resolve()),
                "--add-dir", skill_dir,
                "--model", args.model,
                "-p",
            ],
            stdin=subprocess.PIPE,
            stdout=out_fh,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(output_dir.resolve()),
        )
        proc.stdin.write(prompt)
        proc.stdin.close()
        elapsed = time.time() - start
        print(
            f"[spawn_reviewers] {code} started (pid={proc.pid}, template={template.name}, t+{elapsed:.1f}s)",
            file=sys.stderr,
            flush=True,
        )
        procs.append((code, proc, out_fh, out_path))

    rc_total = 0
    for code, proc, out_fh, out_path in procs:
        if proc is None:
            continue
        rc = proc.wait()
        if out_fh is not None:
            out_fh.close()
        elapsed = time.time() - start
        if rc != 0:
            err = proc.stderr.read() if proc.stderr else ""
            print(
                f"[spawn_reviewers] {code} FAIL rc={rc} (t+{elapsed:.1f}s): {err[:500]}",
                file=sys.stderr,
                flush=True,
            )
            rc_total = max(rc_total, rc)
            continue
        # Content validation — claude -p can exit 0 with empty / truncated output
        # (rate-limit cascade, max-turns cutoff). Treat that as a content failure
        # so the host doesn't silently accept a broken review.
        content = out_path.read_text() if out_path is not None else ""
        size = len(content)
        has_verdict = ("## Verdict" in content) or ("### Verdict" in content)
        if size < 500 or not has_verdict:
            print(
                f"[spawn_reviewers] {code} FAIL_CONTENT (t+{elapsed:.1f}s, size={size}, has_verdict={has_verdict})",
                file=sys.stderr,
                flush=True,
            )
            rc_total = max(rc_total, 1)
            continue
        print(f"[spawn_reviewers] {code} OK (t+{elapsed:.1f}s, size={size})", file=sys.stderr, flush=True)

    return rc_total


if __name__ == "__main__":
    sys.exit(main())
