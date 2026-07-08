# -*- coding: utf-8 -*-
"""Bridge from the IronPython UI engine to a real CPython interpreter.

pyRevit's CPython *launcher* is unreliable on some installs (it throws
"input string '3.12.3' was not in a correct format"), but the bundled
python.exe itself works fine. So the buttons run on the stable IronPython
engine, collect the Revit data, then shell out to python.exe to do the Excel
work with the vendored openpyxl. This keeps the (tested) openpyxl writer and
avoids both the CPython-launcher bug and IronPython's weak COM support.
"""

import os
import io
import json
import glob
import tempfile

from System.Diagnostics import Process, ProcessStartInfo

RUNNER = os.path.join(os.path.dirname(__file__), "runner.py")


def find_python():
    """Locate a CPython interpreter, preferring pyRevit's bundled engine."""
    appdata = os.environ.get("APPDATA", "")
    cands = []
    if appdata:
        cands += glob.glob(os.path.join(appdata, "pyRevit*", "bin", "cengines",
                                        "CPY*", "python.exe"))
    cands = sorted(set(cands))
    if cands:
        return cands[-1]            # highest CPY* version
    # fall back to PATH
    for name in ("python.exe", "python3.exe"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            fp = os.path.join(d, name)
            if os.path.isfile(fp):
                return fp
    return None


def run(payload):
    """Run runner.py under CPython with the given JSON-able payload.

    Returns the parsed JSON the runner prints on stdout. Raises on failure.
    """
    pyexe = find_python()
    if not pyexe:
        raise Exception(
            "Could not find a CPython interpreter. Install pyRevit's CPython "
            "engine (pyRevit Settings) or Python 3 on PATH.")

    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="bkbim_")
    os.close(fd)
    try:
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))

        psi = ProcessStartInfo()
        psi.FileName = pyexe
        psi.Arguments = '"{}" "{}"'.format(RUNNER, tmp)
        psi.UseShellExecute = False
        psi.RedirectStandardOutput = True
        psi.RedirectStandardError = True
        psi.CreateNoWindow = True
        proc = Process.Start(psi)
        stdout = proc.StandardOutput.ReadToEnd()
        stderr = proc.StandardError.ReadToEnd()
        proc.WaitForExit()

        if proc.ExitCode != 0:
            raise Exception((stderr or stdout or "unknown error").strip())
        return json.loads(stdout) if stdout.strip() else {}
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
