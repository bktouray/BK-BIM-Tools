# Git-based installation and updates

Requires Git for Windows on PATH and pyRevit. Close Revit, download
`Install-BKBIMTools.ps1`, then run this in PowerShell from the download folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-BKBIMTools.ps1
```

The installer clones the repository's `main` branch into
`%APPDATA%\pyRevit\Extensions\BKDesigns.extension`. It downloads first, backs up
any existing installation to `%LOCALAPPDATA%\BKBIMTools\InstallBackups` (outside
pyRevit's discovery folders), then installs the clone. Git history and local edits
in a previous installation are preserved in that backup. For a custom pyRevit
extensions directory, pass `-ExtensionsPath 'D:\MyExtensions'`.
Ensure any other copies of BK BIM Tools in custom extension directories are moved
outside those directories to prevent duplicate ribbon tabs.

On Revit startup, a background check runs at most once daily per installation.
It fetches remote history and shows a Windows toast only when updates are
available. It never changes installed source files automatically. Offline and
failed checks stay quiet. Windows notification settings can suppress the toast.
ZIP installations skip this check and the update button explains the migration.

Click **Utilities > Update BK BIM Tools** to fetch and fast-forward the currently
tracked branch. This checks even if the daily check has already run. Restart Revit
after installing updates so cached Python modules reload consistently. No model
elements are modified. Git commands have a 30-second timeout each and do not open
interactive sign-in prompts. For private repos, sign into Git for Windows outside
Revit first. Local modified/untracked files, local commits, missing Git and network
errors are reported without resetting or stashing work. Close other Revit instances
before updating an installation shared between sessions.

Future fixes must be committed and pushed to the branch this clone tracks.
The installer defaults to `main`; merge the setup PR before running it. Merely
editing the cloud workspace does not publish updates. Developer/test installs can
pass `-Branch 'branch-name'`; the updater continues tracking that branch.

## Verification

Off-Revit tests use temporary Git repositories to verify update discovery,
fast-forward installs, dirty/untracked protection, divergence protection, and ZIP
handling. Windows PowerShell, toast notifications and IronPython subprocess behavior
still require a live Windows/Revit test.
