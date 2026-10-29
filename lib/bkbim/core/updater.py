# -*- coding: utf-8 -*-
"""Git-backed updates. Never reset, stash, force, or merge divergent histories."""
import os
import subprocess
import tempfile
import time

from bkbim.core.result import Result


class GitUpdater(object):
    def __init__(self, root, timeout=30):
        self.root = os.path.abspath(root)
        self.timeout = timeout

    def _git(self, *args):
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "Never"
        options = {}
        if os.name == "nt":
            options["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        # A file avoids pipe deadlocks while polling with Python 2.7 subprocess.
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(["git"] + list(args), cwd=self.root,
                                       env=env, stdout=output, stderr=output, **options)
            deadline = time.time() + self.timeout
            while process.poll() is None:
                if time.time() >= deadline:
                    process.kill()
                    process.wait()
                    raise RuntimeError("Git timed out. Check your connection and GitHub sign-in outside Revit.")
                time.sleep(0.05)
            if process.returncode:
                # Do not expose remote URLs or credentials embedded in Git output.
                raise RuntimeError("Git {0} failed. Check Git installation, repository access and GitHub sign-in outside Revit.".format(args[0]))
            output.seek(0)
            return output.read().decode("utf-8", "replace").strip()

    def _validate(self):
        if not os.path.isdir(os.path.join(self.root, ".git")):
            raise ValueError("This is a ZIP installation. Run Install-BKBIMTools.ps1 once to enable Git updates.")
        top = self._git("rev-parse", "--show-toplevel")
        if os.path.normcase(os.path.realpath(top)) != os.path.normcase(os.path.realpath(self.root)):
            raise ValueError("The extension must be the root of its own Git clone.")
        branch = self._git("symbolic-ref", "--short", "HEAD")
        remote = self._git("config", "branch.{0}.remote".format(branch))
        merge_ref = self._git("config", "branch.{0}.merge".format(branch))
        if remote != "origin" or not merge_ref.startswith("refs/heads/"):
            raise ValueError("Use a branch tracking origin before updating.")
        return merge_ref

    def _check(self):
        merge_ref = self._validate()
        self._git("fetch", "--no-tags", "origin", merge_ref)
        # FETCH_HEAD pins the fetched branch, even with unusual fetch refspecs.
        target = self._git("rev-parse", "FETCH_HEAD")
        ahead, behind = [int(n) for n in self._git(
            "rev-list", "--left-right", "--count", "HEAD...{0}".format(target)).split()]
        return {"target": target, "ahead": ahead, "behind": behind}

    def check(self):
        try:
            state = self._check()
            return Result.ok(state, "{0} update commit(s) available.".format(state["behind"]))
        except Exception as exc:
            return Result.fail(str(exc))

    def install(self):
        try:
            self._validate()
            if self._git("status", "--porcelain", "--untracked-files=all"):
                raise ValueError("Local changes found. Commit or back them up outside Revit before updating. Nothing was overwritten.")
            state = self._check()
            if state["ahead"]:
                raise ValueError("This installation has local commits. Resolve them outside Revit before updating.")
            if not state["behind"]:
                return Result.ok(False, "BK BIM Tools is already up to date.")
            self._git("merge", "--ff-only", state["target"])
            return Result.ok(True, "BK BIM Tools updated. Restart Revit to load all changes.")
        except Exception as exc:
            return Result.fail(str(exc))


def extension_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
