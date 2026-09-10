import subprocess

import pytest

from conftest import git
from gitgen.errors import GitgenError
from gitgen.git_context import collect, parse_status, read_diff, run_git


def test_clean_repo(repo):
    assert collect(repo).changes == []


def test_both_layers_and_staged_selection(repo):
    (repo / "app.py").write_text("print('staged')\n")
    git(repo, "add", "app.py")
    (repo / "app.py").write_text("print('unstaged')\n")
    context = collect(repo)
    change = context.changes[0]
    assert change.status == "MM"
    assert change.layers(False) == ["staged", "unstaged"]
    assert change.layers(True) == ["staged"]
    assert "+print('staged')" in read_diff(context, change, "staged")
    assert "+print('unstaged')" in read_diff(context, change, "unstaged")


def test_new_file_in_repository_without_commit(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "new.txt").write_text("first version\n")
    git(tmp_path, "add", "new.txt")
    context = collect(tmp_path)
    assert "+first version" in read_diff(context, context.changes[0], "staged")


@pytest.mark.parametrize("filename", ["한글 이름.txt", "space name.txt", "[literal].txt", ":(glob)*", "new\nline.txt"])
def test_literal_filenames(repo, filename):
    (repo / filename).write_text("unique-content\n")
    git(repo, "--literal-pathspecs", "add", "--", filename)
    context = collect(repo)
    assert context.changes[0].path == filename
    assert "+unique-content" in read_diff(context, context.changes[0], "staged")


def test_rename_preserves_source_path(repo):
    git(repo, "mv", "app.py", "renamed file.py")
    context = collect(repo)
    change = context.changes[0]
    assert change.path == "renamed file.py"
    assert change.old_path == "app.py"
    diff = read_diff(context, change, "staged")
    assert "deleted file" in diff and "new file" in diff


def test_delete_and_binary(repo):
    (repo / "app.py").unlink()
    (repo / "image.bin").write_bytes(b"\x00\x01\x02")
    git(repo, "add", "image.bin")
    context = collect(repo)
    assert "deleted file" in read_diff(context, context.changes[0], "unstaged")
    assert "Binary files" in read_diff(context, context.changes[1], "staged")


def test_untracked_is_status_only(repo):
    (repo / "private.txt").write_text("Do not read")
    change = collect(repo).changes[0]
    assert change.untracked and change.layers(False) == []


def test_outside_and_subdirectory(repo, tmp_path):
    sub = repo / "nested"
    sub.mkdir()
    with pytest.raises(GitgenError, match="루트"):
        collect(sub)


def test_linked_worktree_root(repo, tmp_path_factory):
    location = tmp_path_factory.mktemp("linked") / "worktree"
    git(repo, "worktree", "add", "-b", "linked", str(location))
    assert (location / ".git").is_file()
    assert collect(location).changes == []


@pytest.mark.parametrize("status", [b"UU", b"AA", b"DD", b"AU", b"DU"])
def test_conflicts_are_rejected(status):
    with pytest.raises(GitgenError, match="충돌"):
        parse_status(status + b" app.py\0")


def test_external_diff_not_executed(repo):
    git(repo, "config", "diff.external", "nonexistent-gitgen-diff")
    (repo / "app.py").write_text("changed\n")
    context = collect(repo)
    assert "+changed" in read_diff(context, context.changes[0], "unstaged")


def test_inherited_repository_override_ignored(repo, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/definitely/not/a/repository")
    assert collect(repo).changes == []


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("git", 30)])
def test_git_execution_failure(repo, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(GitgenError):
        run_git(repo, ["status"])
