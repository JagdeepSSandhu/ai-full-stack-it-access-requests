"""Owner-only runtime storage outside Git worktrees."""
import os
from pathlib import Path
import stat


def external_path(path):
    path = Path(path).expanduser().absolute()
    resolved = path.resolve()
    for parent in {path, resolved, *path.parents, *resolved.parents}:
        git = parent / '.git'
        if git.is_file() or (git / 'HEAD').is_file():
            raise ValueError('Use a review location outside Git worktrees')
    return path


def private_directory(path, *, create=True):
    path = external_path(path)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise ValueError('Review directories must be owner-only directories (mode 0700)')
    return path


def private_file(path, flags):
    descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise ValueError('Review files must be regular files owned by the current user')
        if stat.S_IMODE(info.st_mode) != 0o600:
            os.fchmod(descriptor, 0o600)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor
