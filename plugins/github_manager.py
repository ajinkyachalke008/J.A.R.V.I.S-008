"""
plugins/github_manager.py — GitHub & Git Operations Management for JARVIS.

Enables hands-free and voice-driven GitHub workflows:
  1. Inspect authentication status and logged-in GitHub user profile.
  2. List remote repositories with privacy status and latest update times.
  3. View repository issues and pull requests.
  4. Clone remote repositories directly into the user's JarvisProjects directory.
  5. Inspect local git branch and uncommitted working tree changes.
  6. Create new GitHub repositories (gated with HUD confirmation).
  7. Commit and push workspace changes (gated with HUD confirmation).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import confirm
from core import outcome

PLUGIN = {
    "name": "github_manager",
    "description": (
        "Manages GitHub and Git workflows: checks GitHub account status, lists repositories, "
        "inspects repository issues, clones repos into JarvisProjects, checks git status, "
        "creates new repositories, and commits/pushes changes. Use for commands like "
        "'check my GitHub status', 'list my GitHub repositories', 'clone repo <name>', "
        "'view issues for <repo>', 'create GitHub repo', or 'commit and push my changes'. "
        "Irreversible actions (creating repos, pushing commits) require user confirmation on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "The GitHub action to perform. One of: "
                    "'status' (check GitHub login & local git state), "
                    "'list_repos' (list recent repositories), "
                    "'view_issues' (view open issues for a repo), "
                    "'clone_repo' (clone a repository to JarvisProjects), "
                    "'create_repo' (create a new GitHub repository), "
                    "'commit_push' (stage, commit, and push changes to remote)."
                ),
            },
            "repo_name": {
                "type": "STRING",
                "description": "Name of the repository (e.g. 'my-app' or 'owner/my-app').",
            },
            "commit_message": {
                "type": "STRING",
                "description": "Commit message when executing 'commit_push'.",
            },
            "is_private": {
                "type": "BOOLEAN",
                "description": "Whether the new repo should be private (true) or public (false). Default true.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of repositories or issues to list (default 5).",
            },
            "target_dir": {
                "type": "STRING",
                "description": "Directory path for git operations. Defaults to JarvisProjects or workspace.",
            },
        },
        "required": ["action"],
    },
}

_PROJECTS_DIR = Path.home() / "Desktop" / "JarvisProjects"


def _resolve_target_dir(custom_path: Optional[str] = None) -> Path:
    """Resolve target working directory for git operations."""
    if custom_path:
        p = Path(custom_path.strip().strip("\"'")).resolve()
        if p.exists():
            return p
    if _PROJECTS_DIR.exists():
        return _PROJECTS_DIR
    return Path.cwd()


def _run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 25) -> subprocess.CompletedProcess:
    """Run an external CLI command safely with captured UTF-8 output."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )


def _get_gh_user() -> Optional[Dict[str, Any]]:
    """Retrieve logged-in GitHub user info if authenticated."""
    if not shutil.which("gh"):
        return None
    try:
        res = _run_cmd(["gh", "api", "user", "--cache", "60s"])
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return None


def _handle_status(player) -> str:
    """Check GitHub authentication and local git status."""
    if not shutil.which("gh"):
        return "Sir, the GitHub CLI ('gh') is not installed or not in your system PATH."

    user_info = _get_gh_user()
    if not user_info:
        return (
            "Sir, you are not currently signed into GitHub. "
            "Please authenticate via the GitHub login prompt or run 'gh auth login' in your terminal."
        )

    login = user_info.get("login", "Unknown")
    name = user_info.get("name", login)
    public_repos = user_info.get("public_repos", 0)
    total_private = user_info.get("total_private_repos", 0)

    # Check local git status in current workspace
    local_status = ""
    try:
        git_branch = _run_cmd(["git", "branch", "--show-current"])
        if git_branch.returncode == 0 and git_branch.stdout.strip():
            branch = git_branch.stdout.strip()
            git_diff = _run_cmd(["git", "status", "-s"])
            changes = len(git_diff.stdout.strip().splitlines()) if git_diff.stdout.strip() else 0
            local_status = f" Current branch is '{branch}' with {changes} modified file(s)."
    except Exception:
        pass

    msg = (
        f"Sir, you are connected to GitHub as {name} (@{login}). "
        f"You have {public_repos} public and {total_private} private repositories.{local_status}"
    )
    if player:
        player.write_log(f"JARVIS: GitHub status verified for @{login}.")
    return msg


def _handle_list_repos(limit: int, player) -> str:
    """List recent GitHub repositories."""
    if not _get_gh_user():
        return "Sir, please log in to GitHub first so I can fetch your repositories."

    lim = max(1, min(limit or 5, 20))
    try:
        res = _run_cmd(["gh", "repo", "list", "--limit", str(lim), "--json", "name,isPrivate,updatedAt,description"])
        if res.returncode != 0:
            return f"Sir, failed to retrieve repositories: {res.stderr.strip()[:120]}"

        repos = json.loads(res.stdout)
        if not repos:
            return "Sir, you do not have any repositories in your GitHub account."

        repo_lines = []
        for r in repos:
            vis = "Private" if r.get("isPrivate") else "Public"
            name = r.get("name", "Untitled")
            desc = r.get("description") or "No description"
            repo_lines.append(f"• {name} ({vis}) — {desc[:60]}")

        summary = "\n".join(repo_lines)
        if player:
            player.write_log(f"JARVIS: Found {len(repos)} repositories:\n{summary}")

        names = ", ".join(r.get("name", "") for r in repos[:3])
        return f"Sir, here are your latest repositories including {names}. I have detailed them in the activity log."
    except Exception as e:
        return f"Sir, an error occurred while listing repositories: {e}"


def _handle_view_issues(repo_name: str, limit: int, player) -> str:
    """View issues for a specified repository."""
    if not repo_name:
        return "Sir, please specify which repository you would like to view issues for."

    lim = max(1, min(limit or 5, 20))
    try:
        cmd = ["gh", "issue", "list", "--limit", str(lim), "--json", "number,title,author,state"]
        if repo_name and repo_name != "current":
            cmd.extend(["--repo", repo_name])

        res = _run_cmd(cmd)
        if res.returncode != 0:
            return f"Sir, could not retrieve issues for '{repo_name}': {res.stderr.strip()[:120]}"

        issues = json.loads(res.stdout)
        if not issues:
            return f"Sir, there are currently no open issues on {repo_name}."

        lines = [f"#{i['number']}: {i['title']} (by @{i.get('author', {}).get('login', 'anon')})" for i in issues]
        if player:
            player.write_log(f"JARVIS: Open issues for {repo_name}:\n" + "\n".join(lines))

        return f"Sir, found {len(issues)} open issue(s) on {repo_name}: {issues[0]['title']}."
    except Exception as e:
        return f"Sir, could not query issues: {e}"


def _handle_clone_repo(repo_name: str, target_dir: Optional[str], player) -> str:
    """Clone a GitHub repository into JarvisProjects."""
    if not repo_name:
        return "Sir, which repository would you like me to clone?"

    dest_base = _resolve_target_dir(target_dir)
    dest_base.mkdir(parents=True, exist_ok=True)
    clean_name = repo_name.split("/")[-1].replace(".git", "")
    target_path = dest_base / clean_name

    if target_path.exists():
        return f"Sir, the directory '{target_path.name}' already exists at {dest_base}. Clone was skipped."

    try:
        res = _run_cmd(["gh", "repo", "clone", repo_name, str(target_path)])
        if res.returncode == 0:
            if player:
                player.write_log(f"JARVIS: Cloned {repo_name} -> {target_path}")
            return f"Sir, successfully cloned {repo_name} into your JarvisProjects folder."
        else:
            return f"Sir, cloning failed: {res.stderr.strip()[:140]}"
    except Exception as e:
        return f"Sir, clone execution failed: {e}"


def _handle_create_repo(repo_name: str, is_private: bool, target_dir: Optional[str], player) -> str:
    """Create a new GitHub repository gated with HUD confirmation."""
    if not repo_name:
        return "Sir, please provide a name for the new repository."

    dest = _resolve_target_dir(target_dir)
    visibility = "private" if is_private else "public"
    flag = "--private" if is_private else "--public"

    def _execute_create() -> str:
        try:
            cmd = ["gh", "repo", "create", repo_name, flag, "--confirm"]
            res = _run_cmd(cmd, cwd=dest)
            if res.returncode == 0:
                url = res.stdout.strip()
                if player:
                    player.write_log(f"JARVIS: Repository created -> {url}")
                return f"Sir, GitHub repository '{repo_name}' ({visibility}) was successfully created."
            return f"Sir, repository creation failed: {res.stderr.strip()[:120]}"
        except Exception as e:
            return f"Sir, repository creation encountered an error: {e}"

    return confirm.request(
        key=f"gh_create_{repo_name}",
        title=f"Create GitHub Repository: {repo_name}",
        detail=f"This will create a new {visibility.upper()} repository on your GitHub account ({repo_name}).",
        run=_execute_create,
    )


def _handle_commit_push(commit_message: Optional[str], target_dir: Optional[str], player) -> str:
    """Stage, commit, and push changes gated with HUD confirmation."""
    dest = _resolve_target_dir(target_dir)
    msg = commit_message.strip() if commit_message else "Automated update via JARVIS"

    # Inspect changes first
    diff_res = _run_cmd(["git", "status", "-s"], cwd=dest)
    if diff_res.returncode != 0:
        return f"Sir, the directory '{dest.name}' is not an active git repository."

    changes = diff_res.stdout.strip()
    if not changes:
        return f"Sir, there are no changes to commit in '{dest.name}'. Working tree is clean."

    changed_count = len(changes.splitlines())

    def _execute_push() -> str:
        try:
            add_res = _run_cmd(["git", "add", "."], cwd=dest)
            if add_res.returncode != 0:
                return f"Git add failed: {add_res.stderr.strip()}"

            commit_res = _run_cmd(["git", "commit", "-m", msg], cwd=dest)
            if commit_res.returncode != 0:
                return f"Git commit failed: {commit_res.stderr.strip()}"

            push_res = _run_cmd(["git", "push"], cwd=dest, timeout=45)
            if push_res.returncode == 0:
                if player:
                    player.write_log(f"JARVIS: Committed {changed_count} files and pushed to origin: '{msg}'")
                return f"Sir, {changed_count} files committed and pushed to GitHub successfully."
            return f"Push failed: {push_res.stderr.strip()[:140]}"
        except Exception as e:
            return f"Commit and push failed: {e}"

    return confirm.request(
        key=f"gh_push_{dest.name}",
        title=f"Commit & Push: {dest.name}",
        detail=f"Commit {changed_count} file(s) with message '{msg}' and push to origin?",
        run=_execute_push,
    )


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the github_manager plugin."""
    action = str(parameters.get("action", "")).strip().lower()
    repo_name = str(parameters.get("repo_name", "")).strip()
    commit_msg = parameters.get("commit_message")
    is_private = parameters.get("is_private", True)
    limit = parameters.get("limit", 5)
    target_dir = parameters.get("target_dir")

    try:
        if action == "status":
            return _handle_status(player)
        elif action == "list_repos":
            return _handle_list_repos(limit, player)
        elif action == "view_issues":
            return _handle_view_issues(repo_name, limit, player)
        elif action == "clone_repo":
            return _handle_clone_repo(repo_name, target_dir, player)
        elif action == "create_repo":
            return _handle_create_repo(repo_name, is_private, target_dir, player)
        elif action == "commit_push":
            return _handle_commit_push(commit_msg, target_dir, player)
        else:
            return (
                f"Sir, unknown GitHub action '{action}'. "
                "Available actions are: status, list_repos, view_issues, clone_repo, create_repo, and commit_push."
            )
    except Exception as e:
        outcome.notify_failure("github_manager", f"Action '{action}' failed: {e}")
        return f"Sir, GitHub operations encountered an error: {e}"

