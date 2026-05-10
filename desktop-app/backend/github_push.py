"""
github_push.py — Push Code to GitHub
CodeNova IDE: Standalone Git automation script.

Usage:
    python github_push.py '{"project_path": "...", "repo_url": "...", "commit_message": "..."}'

Outputs JSON to stdout on success, error messages to stderr.
"""

import sys
import os
import json
import subprocess


def run_git(args, cwd):
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_current_branch(cwd):
    """Detect the current branch name, defaulting to 'main'."""
    code, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if code == 0 and out:
        return out
    return "main"


def has_remote(cwd, name="origin"):
    """Check whether a named remote already exists."""
    code, out, _ = run_git(["remote"], cwd)
    if code != 0:
        return False
    return name in out.splitlines()


def has_commits(cwd):
    """Check whether the repo has at least one commit."""
    code, _, _ = run_git(["rev-parse", "HEAD"], cwd)
    return code == 0


def main():
    # ── Parse arguments ─────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided."}), file=sys.stderr)
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON argument: {e}"}), file=sys.stderr)
        sys.exit(1)

    project_path = params.get("project_path", "").strip()
    repo_url = params.get("repo_url", "").strip()
    commit_message = params.get("commit_message", "").strip() or "Update from CodeNova IDE"

    if not project_path or not os.path.isdir(project_path):
        print(json.dumps({"error": f"Invalid project path: {project_path}"}), file=sys.stderr)
        sys.exit(1)

    steps = []  # Collect step summaries for the final report

    # ── Step 1: git init (if needed) ────────────────────────────────────
    git_dir = os.path.join(project_path, ".git")
    if not os.path.isdir(git_dir):
        code, out, err = run_git(["init"], project_path)
        if code != 0:
            print(json.dumps({"error": f"git init failed: {err}"}), file=sys.stderr)
            sys.exit(1)
        steps.append("Initialized new Git repository")
    else:
        steps.append("Git repository already initialized")

    # ── Step 2: Configure remote origin ─────────────────────────────────
    if repo_url:
        if has_remote(project_path, "origin"):
            # Update the existing origin URL to match what the user provided
            code, _, err = run_git(["remote", "set-url", "origin", repo_url], project_path)
            if code != 0:
                print(json.dumps({"error": f"Failed to update remote: {err}"}), file=sys.stderr)
                sys.exit(1)
            steps.append(f"Updated origin remote to {repo_url}")
        else:
            code, _, err = run_git(["remote", "add", "origin", repo_url], project_path)
            if code != 0:
                print(json.dumps({"error": f"Failed to add remote: {err}"}), file=sys.stderr)
                sys.exit(1)
            steps.append(f"Added origin remote: {repo_url}")
    else:
        # No URL provided — origin must already exist
        if not has_remote(project_path, "origin"):
            print(json.dumps({"error": "No remote URL provided and no origin remote configured."}), file=sys.stderr)
            sys.exit(1)
        steps.append("Using existing origin remote")

    # ── Step 3: Stage all changes ───────────────────────────────────────
    code, _, err = run_git(["add", "."], project_path)
    if code != 0:
        print(json.dumps({"error": f"git add failed: {err}"}), file=sys.stderr)
        sys.exit(1)
    steps.append("Staged all changes")

    # ── Step 4: Commit (skip gracefully if nothing to commit) ───────────
    code, out, err = run_git(["status", "--porcelain"], project_path)
    has_staged = False
    if code == 0:
        for line in out.splitlines():
            if line and line[0] in ("A", "M", "D", "R", "C"):
                has_staged = True
                break

    if has_staged or not has_commits(project_path):
        code, out, err = run_git(["commit", "-m", commit_message], project_path)
        if code != 0:
            # "nothing to commit" is not a real error
            if "nothing to commit" in (out + err).lower():
                steps.append("Nothing to commit — working tree clean")
            else:
                print(json.dumps({"error": f"git commit failed: {err or out}"}), file=sys.stderr)
                sys.exit(1)
        else:
            steps.append(f"Committed: \"{commit_message}\"")
    else:
        steps.append("Nothing to commit — working tree clean")

    # ── Step 5: Detect branch & push ────────────────────────────────────
    branch = get_current_branch(project_path)
    steps.append(f"Pushing branch: {branch}")

    code, out, err = run_git(["push", "-u", "origin", branch], project_path)
    if code != 0:
        # Provide actionable error info
        combined = (out + " " + err).strip()
        print(json.dumps({"error": f"git push failed: {combined}"}), file=sys.stderr)
        sys.exit(1)

    steps.append("Push successful")

    # ── Done — return success to Electron ───────────────────────────────
    result = {
        "success": True,
        "branch": branch,
        "steps": steps,
        "message": f"Successfully pushed to origin/{branch}",
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
