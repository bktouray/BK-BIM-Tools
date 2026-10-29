# -*- coding: utf-8 -*-
import subprocess
import pytest
from bkbim.core.updater import GitUpdater, extension_root


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path)] + list(args), stderr=subprocess.STDOUT).decode().strip()


@pytest.fixture
def repositories(tmp_path):
    remote = tmp_path / 'remote.git'
    subprocess.check_call(['git', 'init', '--bare', str(remote)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    author = tmp_path / 'author'
    subprocess.check_call(['git', 'clone', str(remote), str(author)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(author, 'config', 'user.name', 'Test')
    git(author, 'config', 'user.email', 'test@example.com')
    git(author, 'checkout', '-b', 'main')
    (author / 'version.txt').write_text('one')
    git(author, 'add', '.')
    git(author, 'commit', '-m', 'initial')
    git(author, 'push', '-u', 'origin', 'main')
    install = tmp_path / 'install'
    subprocess.check_call(['git', 'clone', '--branch', 'main', str(remote), str(install)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(install, 'config', 'user.name', 'Test')
    git(install, 'config', 'user.email', 'test@example.com')
    return author, install


def publish(author):
    (author / 'version.txt').write_text('two')
    git(author, 'commit', '-am', 'update')
    git(author, 'push')


def test_check_does_not_install_but_install_fast_forwards(repositories):
    author, install = repositories
    publish(author)
    updater = GitUpdater(str(install))
    checked = updater.check()
    assert checked.success and checked.value['behind'] == 1
    assert (install / 'version.txt').read_text() == 'one'
    result = updater.install()
    assert result.success and result.value is True
    assert (install / 'version.txt').read_text() == 'two'
    assert git(install, 'rev-parse', 'HEAD') == git(author, 'rev-parse', 'HEAD')


@pytest.mark.parametrize('filename', ['version.txt', 'local.txt'])
def test_modified_and_untracked_files_are_preserved(repositories, filename):
    author, install = repositories
    publish(author)
    before = git(install, 'rev-parse', 'HEAD')
    (install / filename).write_text('my local work')
    result = GitUpdater(str(install)).install()
    assert not result.success and 'Local changes' in result.message
    assert (install / filename).read_text() == 'my local work'
    assert git(install, 'rev-parse', 'HEAD') == before


def test_divergent_local_commit_is_preserved(repositories):
    author, install = repositories
    (install / 'local.txt').write_text('local')
    git(install, 'add', '.')
    git(install, 'commit', '-m', 'local work')
    before = git(install, 'rev-parse', 'HEAD')
    publish(author)
    result = GitUpdater(str(install)).install()
    assert not result.success and 'local commits' in result.message
    assert git(install, 'rev-parse', 'HEAD') == before


def test_up_to_date_is_noop(repositories):
    author, install = repositories
    result = GitUpdater(str(install)).install()
    assert result.success and result.value is False


def test_zip_install_explains_one_time_setup(tmp_path):
    result = GitUpdater(str(tmp_path)).install()
    assert not result.success and 'Install-BKBIMTools.ps1' in result.message


def test_missing_git_returns_failure(repositories, monkeypatch):
    def missing(*args, **kwargs):
        raise OSError('Git not installed')
    monkeypatch.setattr(subprocess, 'Popen', missing)
    result = GitUpdater(str(repositories[1])).check()
    assert not result.success


def test_root_resolves_to_extension_directory():
    from pathlib import Path
    assert (Path(extension_root()) / 'BKBIMTools.tab').is_dir()
