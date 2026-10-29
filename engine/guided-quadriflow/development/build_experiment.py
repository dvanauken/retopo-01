"""Rebuild the frozen experimental engine archive without replacing shipped files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, default=Path('C:/msys64/mingw64'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'manifest.json').read_text(encoding='utf-8'))
    archive = here / 'source.zip'
    digest = sha(archive)
    if digest != manifest['sourceArchiveSha256']:
        raise ValueError('Source archive hash differs from the frozen manifest')
    destination = (args.output or here / 'rebuild').resolve()
    source = destination / ('source-' + digest[:12])
    build = destination / ('build-' + digest[:12])
    source.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            target = (source / info.filename).resolve()
            if os.path.commonpath([str(source), str(target)]) != str(source):
                raise ValueError('Archive member escapes the source directory')
            if not info.is_dir():
                content = package.read(info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != content:
                    raise ValueError(f'Existing extracted source differs: {target}')
                if not target.exists():
                    target.write_bytes(content)
    records = destination / ('record-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    records.mkdir(parents=True)
    bin_dir = args.toolchain.resolve() / 'bin'
    environment = os.environ.copy()
    environment['PATH'] = str(bin_dir) + os.pathsep + environment['PATH']
    commands = [
        [str(bin_dir / 'cmake.exe'), '-S', str(source), '-B', str(build), '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_CXX_COMPILER={(bin_dir / "g++.exe").as_posix()}',
         f'-DCMAKE_MAKE_PROGRAM={(bin_dir / "ninja.exe").as_posix()}',
         '-DCMAKE_POLICY_VERSION_MINIMUM=3.5', f'-DBOOST_ROOT={args.toolchain.as_posix()}',
         '-DBoost_NO_BOOST_CMAKE=ON', f'-DEIGEN_INCLUDE_DIR={(args.toolchain / "include/eigen3").as_posix()}'],
        [str(bin_dir / 'cmake.exe'), '--build', str(build), '-j', str(args.jobs)],
    ]
    record = dict(sourceArchiveSha256=digest, commands=[], tools={})
    for name in ['cmake.exe', 'g++.exe', 'ninja.exe']:
        result = subprocess.run([str(bin_dir / name), '--version'], env=environment, capture_output=True, text=True)
        record['tools'][name] = dict(sha256=sha(bin_dir / name), version=result.stdout.splitlines()[0])
    for index, command in enumerate(commands):
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (records / f'{index}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        record['commands'].append(dict(command=command, exitCode=result.returncode))
        (records / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'Build failed; see {records}')
    executable = build / 'quadriflow.exe'
    record.update(executable=str(executable), executableSha256=sha(executable), passed=True)
    (records / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2))
    # Deliberately do not copy this executable over either shipped package.


if __name__ == '__main__':
    main()
