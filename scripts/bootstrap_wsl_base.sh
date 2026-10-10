#!/usr/bin/env bash
# Trusted bootstrap only. All Linux files are physically inside the approved D: VHD.
set -euo pipefail
test "$(id -u)" = 0
if ! id workbench >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash workbench
fi
test "$(id -u workbench)" != 0
install -d -o workbench -g workbench -m 0750 /opt/workbench
for folder in runtimes tools cache cache/uv cache/pkg evidence source runs tmp state state/codex state/humanize state/dsh; do
    install -d -o workbench -g workbench -m 0750 "/opt/workbench/$folder"
done
if ! test -e /etc/wsl.conf.before-workbench; then
    cp -p /etc/wsl.conf /etc/wsl.conf.before-workbench
fi
cat > /etc/wsl.conf <<'CONFIG'
[boot]
systemd=true
[automount]
enabled=false
mountFsTab=false
[interop]
enabled=false
appendWindowsPath=false
[user]
default=workbench
CONFIG
test -d /sys/kernel/security
if ! mountpoint -q /sys/kernel/security; then
    mount -t securityfs securityfs /sys/kernel/security
fi
python3 - <<'PY'
import ctypes, grp, json, os, platform, pwd
from pathlib import Path
libc = ctypes.CDLL(None, use_errno=True)
abi = libc.syscall(444, 0, 0, 1)
if abi < 4:
    raise SystemExit('Landlock network enforcement is unavailable')
record = {'kernel': platform.release(), 'landlock_abi': abi,
          'lsm': Path('/sys/kernel/security/lsm').read_text().strip(),
          'wsl_configured_for_no_host_mounts_or_interop': True,
          'configuration_active': 'ONLY_AFTER_PROJECT_DISTRO_TERMINATION',
          'model_requests': 0}
Path('/opt/workbench/evidence/base-bootstrap.json').write_text(json.dumps(record, indent=2)+'\n')
os.chown('/opt/workbench/evidence/base-bootstrap.json', pwd.getpwnam('workbench').pw_uid, grp.getgrnam('workbench').gr_gid)
print(json.dumps(record))
PY
