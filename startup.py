# -*- coding: utf-8 -*-
"""Quiet background update notification, at most once per day per installation."""
__persistentengine__ = True

import hashlib
import json
import os
import threading
import time

from bkbim.core.updater import GitUpdater, extension_root


def _check_updates():
    try:
        root = extension_root()
        if not os.path.isdir(os.path.join(root, ".git")):
            return
        state_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BKBIMTools")
        digest = hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
        state_path = os.path.join(state_dir, "update-check-{0}.json".format(digest))
        try:
            with open(state_path, "r") as stream:
                previous = json.load(stream).get("checked_at", 0)
            if 0 <= time.time() - previous < 86400:
                return
        except (IOError, ValueError):
            pass
        result = GitUpdater(root).check()
        if not result.success:
            return  # Offline or unauthenticated startup stays quiet.
        if not os.path.isdir(state_dir):
            os.makedirs(state_dir)
        with open(state_path, "w") as stream:
            json.dump({"checked_at": time.time()}, stream)
        if result.value["behind"] and not result.value["ahead"]:
            from pyrevit import forms
            forms.toast("Updates are available. Use Utilities > Update BK BIM Tools to install.",
                        title="BK BIM Tools")
    except Exception:
        pass  # Notification failures must never prevent Revit from starting.


_worker = threading.Thread(target=_check_updates)
_worker.daemon = True
_worker.start()
