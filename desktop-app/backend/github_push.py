"""
github_push.py — Push Code to GitHub
CodeNova IDE: Standalone Git automation script.

Usage:
    python github_push.py '{"project_path": "...", "repo_url": "...", "commit_message": "...", "token": "..."}'

Outputs JSON to stdout on success, error messages to stderr.
"""

import sys
import os
import json
import subprocess
from urllib.parse import urlparse, urlunparse, quote


# Environment that disables interactive credential prompts so a missing
# password fails fast instead of hanging the spawned subprocess.
NON_INTERACTIVE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "Never",
    "GIT_ASKPASS": "echo",
    "SSH_ASKPASS": "echo",
}


def run_git(args, cwd):
    """Run a git command and return (returncode, stdout, stderr)."""
    env = {**os.environ, **NON_INTERACTIVE_ENV}
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_current_branch(cwd):
    """Detect the current branch name, defaulting to 'main'."""
    code, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if code == 0 and out and out != "HEAD":
        return out
    return "main"


def has_remote(cwd, name="origin"):
    code, out, _ = run_git(["remote"], cwd)
    if code != 0:
        return False
    return name in out.splitlines()


def has_commits(cwd):
    code, _, _ = run_git(["rev-parse", "HEAD"], cwd)
    return code == 0


def inject_token(url: str, token: str) -> str:
    """Embed a Personal Access Token into an https GitHub URL for one push.

    Transforms `https://github.com/user/repo.git`
    into       `https://x-access-token:TOKEN@github.com/user/repo.git`.

    Other URL forms (ssh, git@) are returned unchanged.
    """
    if not token:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    auth_netloc = f"x-access-token:{quote(token, safe='')}@{netloc}"
    return urlunparse((parsed.scheme, auth_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def redact(text: str, token: str) -> str:
    if token and token in text:
        return text.replace(token, "***")
    return text


def fail(message: str, token: str = ""):
    print(json.dumps({"error": redact(message, token)}), file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        fail("No arguments provided.")

    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        fail(f"Invalid JSON argument: {e}")

    project_path = (params.get("project_path") or "").strip()
    repo_url = (params.get("repo_url") or "").strip()
    commit_message = (params.get("commit_message") or "").strip() or "Update from CodeNova IDE"
    token = (params.get("token") or "").strip()

    if not project_path or not os.path.isdir(project_path):
        fail(f"Invalid project path: {project_path}")

    steps = []

    # ── Step 1: git init (if needed) ────────────────────────────────────
    if not os.path.isdir(os.path.join(project_path, ".git")):
        code, _, err = run_git(["init"], project_path)
        if code != 0:
            fail(f"git init failed: {err}")
        steps.append("Initialized new Git repository")
    else:
        steps.append("Git repository already initialized")

    # ── Step 2: Configure remote origin ─────────────────────────────────
    if repo_url:
        if has_remote(project_path, "origin"):
            code, _, err = run_git(["remote", "set-url", "origin", repo_url], project_path)
            if code != 0:
                fail(f"Failed to update remote: {err}")
            steps.append("Updated origin remote")
        else:
            code, _, err = run_git(["remote", "add", "origin", repo_url], project_path)
            if code != 0:
                fail(f"Failed to add remote: {err}")
            steps.append("Added origin remote")
    else:
        if not has_remote(project_path, "origin"):
            fail("No remote URL provided and no origin remote configured.")
        # Read the existing origin URL so token injection (if any) still works.
        code, out, _ = run_git(["remote", "get-url", "origin"], project_path)
        if code == 0 and out:
            repo_url = out
        steps.append("Using existing origin remote")

    # ── Step 3: Stage all changes ───────────────────────────────────────
    code, _, err = run_git(["add", "."], project_path)
    if code != 0:
        fail(f"git add failed: {err}")
    steps.append("Staged all changes")

    # ── Step 4: Commit (skip gracefully if nothing to commit) ───────────
    code, out, err = run_git(["status", "--porcelain"], project_path)
    has_staged = False
    if code == 0:
        for line in out.splitlines():
            # Index column = first char; modified/added/etc means staged.
            if line and line[0] in ("A", "M", "D", "R", "C"):
                has_staged = True
                break

    if has_staged or not has_commits(project_path):
        code, out, err = run_git(["commit", "-m", commit_message], project_path)
        if code != 0:
            combined = (out + " " + err).lower()
            if "nothing to commit" in combined:
                steps.append("Nothing to commit — working tree clean")
            elif "please tell me who you are" in combined or "empty ident" in combined:
                fail("Git identity not configured. Run: git config --global user.email \"you@example.com\" "
                     "and git config --global user.name \"Your Name\".")
            else:
                fail(f"git commit failed: {err or out}")
        else:
            steps.append(f'Committed: "{commit_message}"')
    else:
        steps.append("Nothing to commit — working tree clean")

    # ── Step 5: Detect branch & push ────────────────────────────────────
    branch = get_current_branch(project_path)
    steps.append(f"Pushing branch: {branch}")

    # If a token was provided, push to a tokenised URL directly so the
    # subprocess never needs to prompt for credentials. The remote config
    # stays clean (we don't write the token into .git/config).
    push_target = inject_token(repo_url, token) if (token and repo_url) else "origin"

    push_args = ["push", "-u", push_target, branch] if push_target != "origin" else ["push", "-u", "origin", branch]
    code, out, err = run_git(push_args, project_path)

    if code != 0:
        combined = (out + " " + err).strip()
        low = combined.lower()
        if "src refspec" in low and "does not match" in low:
            fail(f"Nothing to push on branch '{branch}'. Create at least one commit first.", token)
        if "could not read username" in low or "authentication failed" in low or "invalid username or password" in low:
            fail("Authentication failed. Provide a GitHub Personal Access Token in the push dialog "
                 "(or configure SSH).", token)
        if "rejected" in low and ("non-fast-forward" in low or "fetch first" in low):
            fail("Remote has commits you don't have locally. Pull first, or use a fresh repository.", token)
        if "could not resolve host" in low:
            fail("Network error — could not reach the GitHub host. Check your internet connection.", token)
        fail(f"git push failed: {combined}", token)

    steps.append("Push successful")

    result = {
        "success": True,
        "branch": branch,
        "steps": steps,
        "message": f"Successfully pushed to origin/{branch}",
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
