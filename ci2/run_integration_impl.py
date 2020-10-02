
import os
import subprocess

from impulse.ci2 import integration
from impulse.util import temp_dir


def Run(cmd):
  yield ' '.join(cmd)
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  while True:
    output = p.stdout.readline().decode('utf-8').rstrip()
    if output == '' and p.poll() != None:
      break
    if output:
      yield output.strip()
  if p.poll() != 0:
    raise ValueError('Execution bug')


def RunIntegrationTest(job):
  if not job.authenticated:
    yield 'Unauthenticated build'
    raise ValueError('Unauthenticated')

  with temp_dir.ScopedTempDirectory(delete_non_empty=True):
    workdir = os.getcwd()

    yield from CreateRepo(job.repo_name)
    yield from CheckoutUpstreamBranch(
      job.repo_name, 'head', job.repo_merge_from, job.branch_merge_from)
    yield from CheckoutUpstreamBranch(
      job.repo_name, 'base', job.repo_merge_into, job.branch_merge_into)
    yield from Rebase(
      job.repo_name, job.branch_merge_into, job.branch_merge_from)

    if job.repo_name != 'impulse':
      yield from CreateRepo('impulse')
      yield from CheckoutRepo(
        'impulse', 'https://github.com/tmathmeyer/impulse', 'master')

    yield from Run(['ln', '-s', 'impulse/rules', 'rules'])
    yield from Run([
      'impulse', 'build', '--debug', '--force', '--fakeroot', workdir,
      '//impulse:impulse'
    ])
    yield from Run([
      './GENERATED/BINARIES/impulse/impulse',
      'testsuite', '--notermcolor', '--debug', '--fakeroot', workdir
    ])


def CreateRepo(repo_name):
  yield from Run(['mkdir', repo_name])
  with temp_dir.ScopedTempDirectory(repo_name):
    yield from Run(['git', 'init'])


def CheckoutUpstreamBranch(repo_name, local_name, repo_url, remote_name):
  with temp_dir.ScopedTempDirectory(repo_name):
    yield from Run(['git', 'remote', 'add', local_name, repo_url])
    yield from Run(['git', 'fetch', local_name])
    yield from Run([
      'git', 'checkout', '--track', f'{local_name}/{remote_name}'
    ])


def Rebase(repo_name, base, head):
  with temp_dir.ScopedTempDirectory(repo_name):
    yield from Run(['git', 'checkout', base])
    yield from Run(['git', 'rebase', head])
