import os
import pytest

from mock import patch

from bumper import BumpAccident
from bumper.utils import PyPI

from workspace.commands.bump import bump
from workspace.commands.clean import clean
from workspace.commands.commit import commit
from workspace.commands.diff import diff
from workspace.commands.log import show_log
from workspace.commands.push import push
from workspace.commands.setup import setup as wst_setup
from workspace.commands.test import test as wst_test
from workspace.commands.status import status
from workspace.scm import stat_repo, all_branches, commit_logs
from workspace.utils import RunError

from test_stubs import temp_dir, temp_git_repo, temp_remote_git_repo


@pytest.mark.parametrize('command,exception', [(diff, None), (show_log, SystemExit), (status, None)])
def test_sanity(command, exception):
  with temp_dir():
    if exception:
      with pytest.raises(exception):
        command()
    else:
      command()

  with temp_git_repo():
    command()


def test_bump():
  with temp_dir():
    with pytest.raises(SystemExit):
      bump()

  with temp_remote_git_repo():
    # No requirements.txt
    if os.path.exists('requirements.txt'):
      os.unlink('requirements.txt')
    with pytest.raises(BumpAccident):
      bump()

    # All requirements are up to date
    with open('requirements.txt', 'w') as fp:
      fp.write('localconfig\nrequests')
    assert ({}, None, []) == bump()

    # All requirements are outdated
    with open('requirements.txt', 'w') as fp:
      fp.write('# Comment for localconfig\nlocalconfig==0.0.1\n# Comment for requests\nrequests<0.1')
    msgs, commit_msg, bumps = bump()
    file, msg = msgs.items()[0]
    version = PyPI.latest_package_version('localconfig')
    assert 'requirements.txt' == file

    expected_msg = 'Require localconfig==%s' % version
    assert expected_msg == msg[:len(expected_msg)]
    assert expected_msg == commit_msg[:len(expected_msg)]

    with open('requirements.txt') as fp:
      requirements = fp.read()
      assert '# Comment for localconfig\nlocalconfig==%s\n# Comment for requests\nrequests<0.1\n' % version == requirements


def test_clean():
  with temp_dir():
    clean()


def test_commit():
  with temp_dir():
    with pytest.raises(SystemExit):
      commit()

  with temp_git_repo():
    with pytest.raises(RunError):
      commit('no files to commit')

    with open('new_file', 'w') as fp:
      fp.write('Hello World')
    assert 'new_file' in stat_repo(return_output=True)

    commit('Add new file', branch='master')

    assert 'working directory clean' in stat_repo(return_output=True)
    assert 'Hello World' == open('new_file').read()

    with open('new_file', 'w') as fp:
      fp.write('New World')

    commit('Update file', branch='updated')

    assert ['updated', 'master'] == all_branches()

    commit(move=['moved'])

    assert ['updated', 'master', 'moved'] == all_branches()

    commit(discard=True)

    assert ['master', 'moved'] == all_branches()

    logs = commit_logs()
    assert 'new file' in logs
    assert 1 == len(filter(None, logs.split('commit')))


def test_test():
  with temp_dir():
    with pytest.raises(SystemExit):
      wst_test()

  with temp_git_repo():
    with pytest.raises(IOError):
      wst_test()
    wst_setup(product=True)

    pass_test = 'def test_pass():\n  assert True'
    fail_test = 'def test_fail():\n  assert False'

    with open('test/test_pass.py', 'w') as fp:
      fp.write(pass_test)
    commands = wst_test()
    assert 'py27' in commands
    assert 'tox' in commands['py27']

    with open('test/test_fail.py', 'w') as fp:
      fp.write(fail_test + '\n' + pass_test)
    with pytest.raises(SystemExit):
      wst_test()

    commands = wst_test(['test/test_pass.py'])
    assert 'py27' in commands
    assert 'py.test' in commands['py27']

    os.utime('requirements.txt', None)
    commands = wst_test(match_test='test_pass', show_output=True)
    assert 'py27' in commands
    assert 'tox' in commands['py27']

    with pytest.raises(SystemExit):
      wst_test(['style'])
    with open('test/test_fail.py', 'w') as fp:
      fp.write(fail_test + '\n\n\n' + pass_test)
    assert 'style' in wst_test(['style'])

    os.unlink('test/test_fail.py')
    assert 'coverage' in wst_test(['coverage'])
    assert os.path.exists('coverage.xml')
    assert os.path.exists('htmlcov/index.html')


@patch('workspace.commands.push.push_repo')
def test_push(*_):
  with temp_dir():
    with pytest.raises(SystemExit):
      push()

  with temp_remote_git_repo():
    push()

    with open('new_file', 'w') as fp:
      fp.write('Hello World')
    assert 'new_file' in stat_repo(return_output=True)

    commit('Add new file', branch='new_file')

    push()

    assert ['master'] == all_branches()
    assert "ahead of 'origin/master' by 1 commit." in stat_repo(return_output=True)
