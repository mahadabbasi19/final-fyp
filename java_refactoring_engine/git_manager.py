"""
Git Manager Module for CodeNova IDE
====================================
Provides a high-level, IDE-oriented interface over GitPython for the
desktop application's **Source Control** panel.

Capabilities
------------
* Repository discovery & initialisation
* Status queries (modified / staged / untracked / conflicts)
* Staging, unstaging, and discarding changes
* Committing with messages
* Branch management (list / create / switch / delete)
* Remote operations (push / pull / fetch) with SSH & HTTPS support
* Diff generation (working-tree, staged, commit-to-commit)
* Conflict detection helpers
* Log / history retrieval

All public functions return **plain dictionaries** so they can be
serialised directly by FastAPI / Pydantic without conversion.

Author: CodeNova IDE – Java Refactoring Engine
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import git
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError


# ──────────────────────────────────────────────────────────────────────
# Enumerations & data types
# ──────────────────────────────────────────────────────────────────────

class FileStatus(str, Enum):
    """Git file status codes (mirrors ``git status --porcelain``)."""
    MODIFIED    = "modified"
    ADDED       = "added"
    DELETED     = "deleted"
    RENAMED     = "renamed"
    UNTRACKED   = "untracked"
    CONFLICT    = "conflict"
    STAGED      = "staged"
    IGNORED     = "ignored"


@dataclass
class GitFileChange:
    """One changed file with its path and status."""
    path: str
    status: str            # FileStatus value
    staged: bool = False
    old_path: Optional[str] = None  # for renames

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GitLogEntry:
    """A single commit in the log."""
    sha: str
    short_sha: str
    message: str
    author: str
    author_email: str
    date: str              # ISO-8601 string
    parents: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────

class GitManagerError(Exception):
    """Base exception for git_manager operations."""


class NotARepoError(GitManagerError):
    """Raised when the target path is not inside a Git repository."""


class ConflictError(GitManagerError):
    """Raised when an operation cannot proceed due to merge conflicts."""


# ──────────────────────────────────────────────────────────────────────
# GitManager
# ──────────────────────────────────────────────────────────────────────

class GitManager:
    """High-level Git operations for the CodeNova desktop IDE.

    Parameters
    ----------
    repo_path : str | Path
        The working directory (or any subdirectory) of a Git repository.
        If no ``.git`` folder is found, ``init_repo()`` can create one.
    """

    def __init__(self, repo_path: Optional[str] = None) -> None:
        self._repo: Optional[Repo] = None
        self._repo_path: Optional[str] = None
        if repo_path:
            self.open(repo_path)

    # ── Repository lifecycle ──────────────────────────────────────

    def open(self, repo_path: str) -> Dict[str, Any]:
        """Open an existing Git repository.

        Returns a summary dict with repo root, current branch, etc.
        Raises ``NotARepoError`` if the path is not under Git control.
        """
        try:
            self._repo = Repo(repo_path, search_parent_directories=True)
            self._repo_path = self._repo.working_dir
            return self._repo_summary()
        except (InvalidGitRepositoryError, NoSuchPathError) as exc:
            self._repo = None
            self._repo_path = None
            raise NotARepoError(f"Not a Git repository: {repo_path}") from exc

    def init_repo(self, path: str) -> Dict[str, Any]:
        """Initialise a new Git repository at *path*."""
        os.makedirs(path, exist_ok=True)
        self._repo = Repo.init(path)
        self._repo_path = self._repo.working_dir
        return self._repo_summary()

    @property
    def is_open(self) -> bool:
        return self._repo is not None

    def _require_repo(self) -> Repo:
        if self._repo is None:
            raise NotARepoError("No repository is open. Call open() or init_repo() first.")
        return self._repo

    def _repo_summary(self) -> Dict[str, Any]:
        repo = self._require_repo()
        return {
            "root": repo.working_dir,
            "branch": self._current_branch_name(repo),
            "is_dirty": repo.is_dirty(untracked_files=True),
            "has_remotes": len(repo.remotes) > 0,
            "remotes": [r.name for r in repo.remotes],
        }

    @staticmethod
    def _current_branch_name(repo: Repo) -> str:
        try:
            return repo.active_branch.name
        except TypeError:
            # Detached HEAD
            return f"HEAD@{repo.head.commit.hexsha[:7]}"

    # ── Status ────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return the full working-tree status.

        Returns
        -------
        dict
            ``branch``, ``is_dirty``, ``changes`` (list of GitFileChange dicts),
            ``staged_count``, ``modified_count``, ``untracked_count``,
            ``conflict_count``.
        """
        repo = self._require_repo()
        changes: List[Dict] = []

        # Staged changes (index vs HEAD)
        try:
            staged_diffs = repo.index.diff("HEAD")
        except git.exc.BadName:
            # No commits yet – everything in index is "new"
            staged_diffs = []

        for d in staged_diffs:
            status = self._diff_to_status(d)
            changes.append(GitFileChange(
                path=d.b_path or d.a_path,
                status=status,
                staged=True,
                old_path=d.a_path if d.renamed_file else None,
            ).to_dict())

        # Unstaged changes (working tree vs index)
        for d in repo.index.diff(None):
            status = self._diff_to_status(d)
            changes.append(GitFileChange(
                path=d.b_path or d.a_path,
                status=status,
                staged=False,
            ).to_dict())

        # Untracked files
        for f in repo.untracked_files:
            changes.append(GitFileChange(
                path=f,
                status=FileStatus.UNTRACKED.value,
                staged=False,
            ).to_dict())

        # Conflict detection
        conflicts = self._detect_conflicts(repo)
        for p in conflicts:
            # If already listed, update status; otherwise add
            found = False
            for c in changes:
                if c["path"] == p:
                    c["status"] = FileStatus.CONFLICT.value
                    found = True
                    break
            if not found:
                changes.append(GitFileChange(
                    path=p, status=FileStatus.CONFLICT.value, staged=False,
                ).to_dict())

        staged_count = sum(1 for c in changes if c.get("staged"))
        modified_count = sum(1 for c in changes if c["status"] == FileStatus.MODIFIED.value)
        untracked_count = sum(1 for c in changes if c["status"] == FileStatus.UNTRACKED.value)
        conflict_count = len(conflicts)

        return {
            "branch": self._current_branch_name(repo),
            "is_dirty": repo.is_dirty(untracked_files=True),
            "changes": changes,
            "staged_count": staged_count,
            "modified_count": modified_count,
            "untracked_count": untracked_count,
            "conflict_count": conflict_count,
        }

    @staticmethod
    def _diff_to_status(diff) -> str:
        if diff.renamed_file:
            return FileStatus.RENAMED.value
        if diff.deleted_file:
            return FileStatus.DELETED.value
        if diff.new_file:
            return FileStatus.ADDED.value
        return FileStatus.MODIFIED.value

    @staticmethod
    def _detect_conflicts(repo: Repo) -> List[str]:
        """Return list of paths with unresolved merge conflicts."""
        conflicts: List[str] = []
        try:
            unmerged = repo.index.unmerged_blobs()
            for path in unmerged:
                conflicts.append(path)
        except Exception:
            pass
        return conflicts

    # ── Staging / Unstaging ───────────────────────────────────────

    def stage_files(self, paths: List[str]) -> Dict[str, Any]:
        """Stage (add) one or more files to the index.

        Parameters
        ----------
        paths : list[str]
            Relative paths from the repo root.  Use ``["."]`` to stage all.
        """
        repo = self._require_repo()
        repo.index.add(paths)
        return {"staged": paths, "status": "ok"}

    def stage_all(self) -> Dict[str, Any]:
        """Stage all changes including untracked files."""
        repo = self._require_repo()
        repo.git.add(A=True)
        return {"staged": "all", "status": "ok"}

    def unstage_files(self, paths: List[str]) -> Dict[str, Any]:
        """Remove files from the staging area (keep working-tree changes)."""
        repo = self._require_repo()
        repo.git.reset("HEAD", "--", *paths)
        return {"unstaged": paths, "status": "ok"}

    def discard_changes(self, paths: List[str]) -> Dict[str, Any]:
        """Discard working-tree changes for the given files."""
        repo = self._require_repo()
        repo.git.checkout("--", *paths)
        return {"discarded": paths, "status": "ok"}

    # ── Commit ────────────────────────────────────────────────────

    def commit(self, message: str, author: Optional[str] = None) -> Dict[str, Any]:
        """Create a commit with the currently staged changes.

        Parameters
        ----------
        message : str
            Commit message (required, non-empty).
        author : str | None
            Override string in ``"Name <email>"`` format.
        """
        if not message or not message.strip():
            raise GitManagerError("Commit message cannot be empty.")

        repo = self._require_repo()

        kwargs: Dict[str, Any] = {"m": message}
        if author:
            kwargs["author"] = author

        try:
            repo.index.commit(message)
        except Exception as exc:
            raise GitManagerError(f"Commit failed: {exc}") from exc

        head = repo.head.commit
        return {
            "sha": head.hexsha,
            "short_sha": head.hexsha[:7],
            "message": head.message.strip(),
            "author": str(head.author),
            "date": head.committed_datetime.isoformat(),
            "status": "ok",
        }

    # ── Branch management ─────────────────────────────────────────

    def list_branches(self) -> Dict[str, Any]:
        repo = self._require_repo()
        current = self._current_branch_name(repo)
        local = [b.name for b in repo.branches]
        remote = []
        for ref in repo.remotes[0].refs if repo.remotes else []:
            remote.append(ref.remote_head)
        return {
            "current": current,
            "local": local,
            "remote": remote,
        }

    def create_branch(self, name: str, checkout: bool = True) -> Dict[str, Any]:
        """Create a new branch. Optionally switch to it."""
        repo = self._require_repo()
        if name in [b.name for b in repo.branches]:
            raise GitManagerError(f"Branch '{name}' already exists.")
        new_branch = repo.create_head(name)
        if checkout:
            new_branch.checkout()
        return {
            "branch": name,
            "checked_out": checkout,
            "status": "ok",
        }

    def switch_branch(self, name: str) -> Dict[str, Any]:
        """Switch to an existing branch."""
        repo = self._require_repo()
        if repo.is_dirty(untracked_files=False):
            raise GitManagerError(
                "Cannot switch branches with uncommitted changes. "
                "Commit or stash your changes first."
            )
        try:
            repo.git.checkout(name)
        except GitCommandError as exc:
            raise GitManagerError(f"Failed to switch to '{name}': {exc}") from exc
        return {"branch": name, "status": "ok"}

    def delete_branch(self, name: str, force: bool = False) -> Dict[str, Any]:
        """Delete a local branch."""
        repo = self._require_repo()
        current = self._current_branch_name(repo)
        if name == current:
            raise GitManagerError("Cannot delete the currently checked-out branch.")
        try:
            repo.delete_head(name, force=force)
        except GitCommandError as exc:
            raise GitManagerError(f"Failed to delete branch '{name}': {exc}") from exc
        return {"deleted": name, "status": "ok"}

    # ── Remote operations ─────────────────────────────────────────

    def push_to_remote(
        self,
        remote_name: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
    ) -> Dict[str, Any]:
        """Push to a remote repository.

        Supports both SSH and HTTPS authentication patterns:
        - SSH: relies on the user's ssh-agent / key configuration.
        - HTTPS: relies on Git credential helpers already configured.
        """
        repo = self._require_repo()
        if not repo.remotes:
            raise GitManagerError("No remotes configured. Add a remote first.")

        remote = repo.remote(remote_name)
        branch = branch or self._current_branch_name(repo)

        args = [branch]
        kwargs: Dict[str, Any] = {}
        if set_upstream:
            kwargs["set_upstream"] = True

        try:
            info_list = remote.push(*args, **kwargs)
            results = []
            for info in info_list:
                results.append({
                    "local_ref": str(info.local_ref) if info.local_ref else None,
                    "remote_ref": str(info.remote_ref_string),
                    "flags": info.flags,
                    "summary": info.summary.strip(),
                })
            return {"remote": remote_name, "branch": branch, "push_info": results, "status": "ok"}
        except GitCommandError as exc:
            raise GitManagerError(f"Push failed: {exc}") from exc

    def pull_from_remote(self, remote_name: str = "origin") -> Dict[str, Any]:
        """Pull (fetch + merge) from a remote."""
        repo = self._require_repo()
        if not repo.remotes:
            raise GitManagerError("No remotes configured.")
        remote = repo.remote(remote_name)
        try:
            info_list = remote.pull()
            results = []
            for info in info_list:
                results.append({
                    "ref": str(info.ref),
                    "flags": info.flags,
                    "note": info.note,
                })
            # Check if pull created conflicts
            conflicts = self._detect_conflicts(repo)
            return {
                "remote": remote_name,
                "pull_info": results,
                "conflicts": conflicts,
                "status": "conflict" if conflicts else "ok",
            }
        except GitCommandError as exc:
            raise GitManagerError(f"Pull failed: {exc}") from exc

    def fetch_remote(self, remote_name: str = "origin") -> Dict[str, Any]:
        """Fetch updates from a remote without merging."""
        repo = self._require_repo()
        if not repo.remotes:
            raise GitManagerError("No remotes configured.")
        remote = repo.remote(remote_name)
        try:
            info_list = remote.fetch()
            results = []
            for info in info_list:
                results.append({
                    "ref": str(info.ref),
                    "flags": info.flags,
                    "note": info.note,
                })
            return {"remote": remote_name, "fetch_info": results, "status": "ok"}
        except GitCommandError as exc:
            raise GitManagerError(f"Fetch failed: {exc}") from exc

    def add_remote(self, name: str, url: str) -> Dict[str, Any]:
        """Add a new remote."""
        repo = self._require_repo()
        try:
            repo.create_remote(name, url)
        except GitCommandError as exc:
            raise GitManagerError(f"Failed to add remote: {exc}") from exc
        return {"remote": name, "url": url, "status": "ok"}

    # ── Diff ──────────────────────────────────────────────────────

    def get_diff(
        self,
        path: Optional[str] = None,
        staged: bool = False,
    ) -> Dict[str, Any]:
        """Get the diff for the working tree or staged changes.

        Parameters
        ----------
        path : str | None
            Restrict diff to one file. ``None`` means all files.
        staged : bool
            If True, show staged (index vs HEAD) diff.
        """
        repo = self._require_repo()

        args = []
        if staged:
            try:
                diffs = repo.index.diff("HEAD", create_patch=True)
            except git.exc.BadName:
                diffs = []
        else:
            diffs = repo.index.diff(None, create_patch=True)

        entries = []
        for d in diffs:
            file_path = d.b_path or d.a_path
            if path and file_path != path:
                continue
            diff_text = d.diff
            if isinstance(diff_text, bytes):
                diff_text = diff_text.decode("utf-8", errors="replace")
            entries.append({
                "path": file_path,
                "status": self._diff_to_status(d),
                "diff": diff_text,
            })

        return {"diffs": entries, "count": len(entries)}

    # ── Log / History ─────────────────────────────────────────────

    def get_log(self, max_count: int = 50, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Return recent commit log entries.

        Parameters
        ----------
        max_count : int
            Maximum number of commits to return.
        file_path : str | None
            If given, only list commits that touch this file.
        """
        repo = self._require_repo()
        kwargs: Dict[str, Any] = {"max_count": max_count}
        if file_path:
            kwargs["paths"] = file_path

        entries = []
        try:
            for commit in repo.iter_commits(**kwargs):
                entries.append(GitLogEntry(
                    sha=commit.hexsha,
                    short_sha=commit.hexsha[:7],
                    message=commit.message.strip(),
                    author=str(commit.author),
                    author_email=commit.author.email,
                    date=commit.committed_datetime.isoformat(),
                    parents=[p.hexsha[:7] for p in commit.parents],
                ).to_dict())
        except Exception:
            pass  # empty repo – no commits yet

        return {"commits": entries, "count": len(entries)}

    # ── Stash ─────────────────────────────────────────────────────

    def stash_save(self, message: Optional[str] = None) -> Dict[str, Any]:
        """Stash current changes."""
        repo = self._require_repo()
        args = ["save"]
        if message:
            args.append(message)
        try:
            result = repo.git.stash(*args)
            return {"result": result, "status": "ok"}
        except GitCommandError as exc:
            raise GitManagerError(f"Stash failed: {exc}") from exc

    def stash_pop(self) -> Dict[str, Any]:
        """Pop the most recent stash."""
        repo = self._require_repo()
        try:
            result = repo.git.stash("pop")
            return {"result": result, "status": "ok"}
        except GitCommandError as exc:
            raise GitManagerError(f"Stash pop failed: {exc}") from exc

    def stash_list(self) -> Dict[str, Any]:
        """List all stash entries."""
        repo = self._require_repo()
        try:
            raw = repo.git.stash("list")
            stashes = [line for line in raw.split("\n") if line.strip()]
            return {"stashes": stashes, "count": len(stashes)}
        except GitCommandError:
            return {"stashes": [], "count": 0}
