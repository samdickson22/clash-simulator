"""Offline candidate: use only after coordinator authorizes changing private R.

Construct a narrow tree using a temporary index. Keep the Mac source commit as
a second parent for barrier ancestry; never merge public-main's tree wholesale.
Does not check out the result or change the caller's index. Never push its ref.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from release_run import CANONICAL, PRIVATE_COMMIT, PRIVATE_REF, DESCENDANT_ALLOWLIST, MAC_DIRECTORY, require


def build_descendant(repo, source_commit, private_ref):
    require(private_ref.startswith('refs/private/'), 'local private ref required')
    require(private_ref != PRIVATE_REF, 'registration protection ref cannot be a target')
    def git(*args, env=None, data=None):
        return subprocess.check_output(['git', '--no-optional-locks', '-C', str(repo), *args],
                                       env=env, input=data, text=True).strip()
    require(git('rev-parse', PRIVATE_REF) == PRIVATE_COMMIT, 'registration protection ref changed before build')
    source_commit = git('rev-parse', source_commit + '^{commit}')
    require(git('status', '--porcelain', '--ignored') == '', 'checkout must be clean')
    source_mac_paths = set(git('ls-tree', '-r', '--name-only', source_commit, '--', MAC_DIRECTORY).splitlines())
    require(source_mac_paths <= DESCENDANT_ALLOWLIST, 'unlisted Mac/classification path requires ruling')
    with tempfile.TemporaryDirectory(prefix='t1-mac-descendant-index-') as tmp:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        git('read-tree', PRIVATE_COMMIT, env=env)
        copied = []
        for name in sorted(DESCENDANT_ALLOWLIST):
            row = git('ls-tree', source_commit, '--', name)
            if not row:
                continue
            metadata, actual = row.split('\t')
            mode, kind, blob = metadata.split()
            require(actual == name and mode == '100644' and kind == 'blob', 'regular metadata blob required')
            git('update-index', '--add', '--cacheinfo', mode + ',' + blob + ',' + name, env=env)
            copied.append(name)
        require(copied, 'no allowed Mac metadata in source')
        tree = git('write-tree', env=env)
        commit = git('commit-tree', tree, '-p', PRIVATE_COMMIT, '-p', source_commit,
                     data='PRIVATE: narrow TIERS Mac route descendant; never push\n')
        changed = set(git('diff', '--no-renames', '--name-only', PRIVATE_COMMIT, commit).splitlines())
        require(changed <= DESCENDANT_ALLOWLIST, 'descendant escaped exact allowlist')
        git('update-ref', private_ref, commit, '0' * 40)
        require(git('rev-parse', PRIVATE_REF) == PRIVATE_COMMIT, 'registration protection ref changed after build')
        return dict(commit=commit, tree=tree, private_ref=private_ref, source_commit=source_commit,
                    base_commit=PRIVATE_COMMIT, changed_paths=sorted(changed), copied_paths=copied,
                    checked_out=False, never_push=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--private-ref', required=True)
    args = parser.parse_args()
    import json
    print(json.dumps(build_descendant(CANONICAL, args.source_commit, args.private_ref)))


if __name__ == '__main__':
    main()
