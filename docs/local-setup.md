# 本地可复现的 P0 准备

工作区：`D:\Desktop\Enhanced_Humanizer`；Windows 11 x64。已复用 Git/gh/uv/Node/Codex/Conda，未升级全局工具。新 Python 3.13.14、32 项锁定 wheel、`.venv`、缓存和审计证据都在项目下。

PowerShell 项目会话：

```powershell
Set-Location 'D:\Desktop\Enhanced_Humanizer'
$env:UV_CACHE_DIR = "$PWD\.local-workbench\cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.local-workbench\runtimes\python"
$env:HUMANIZE_HOME = "$PWD\.local-workbench\humanize"
$env:HUMANIZE_SENTRY = 'off'
$env:DSH_HOME = "$PWD\.local-workbench\dsh"
$env:XDG_CACHE_HOME = "$PWD\.local-workbench\cache"
$env:PKG_NATIVE_CACHE_PATH = "$PWD\.local-workbench\cache\pkg"
uv venv --python 3.13.14 .venv
uv pip sync --python .venv/Scripts/python.exe --require-hashes --no-build configs/requirements-p0-windows.lock
```

仅在目标 `.venv` 不存在时创建，不对他人已有环境执行覆盖。安装使用已发布 wheel，不 clone 上游源码。完整 lock 含传递依赖和 SHA256；`configs/upstreams.lock.json` 的源码 SHA 是审核候选，不能混作已安装 wheel 对应 commit。源码 Fork/checkout 后另行验证许可证与版本映射。

可运行的无模型调用检查：

```powershell
python scripts/audit_environment.py
python scripts/check_repository.py
python -m unittest discover -s tests -v
.\.venv\Scripts\hmz.exe --version
.\.venv\Scripts\python.exe scripts/probe_humanize.py
.\.venv\Scripts\python.exe scripts/probe_dsh_initialize.py
```

`audit_environment.py --network` 才启用只读 GitHub 和 DeepSeek 模型列表查询，仍不发起推理。DSH 初始化探针明确不发送 prompt、不带 key，并重定向 runtime/native/temp 路径。官方 fake driver 只验证接口及轮次间预算，不能替代真实模型 demo。

机密扫描：项目已下载官方 Gitleaks 8.30.1 到 `.local-workbench/tools/gitleaks/8.30.1/`，zip SHA256 为 `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`，与官方 release asset digest 核对。其他机器从 [官方发布页](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)取得对应平台二进制并核对官方 checksum；不复用 Windows zip 到 Linux。

```powershell
.\.local-workbench\tools\gitleaks\8.30.1\gitleaks.exe git --staged --redact --no-banner
.\.local-workbench\tools\gitleaks\8.30.1\gitleaks.exe git --redact --no-banner
git config --local core.hooksPath .githooks
```

P0 费用已获批，限额见 configs/budget-proposal.json；无工具的直接 API 探针为 `node scripts/probe_deepseek_api.mjs`，logprobs 变体加 `--logprobs`。它使用持久 ledger + 独占锁、调用前按峰值价预留整个模型 context 和封顶输出、不重试、不跟随重定向，失败也保留预留；只用于此固定文本探针，不是通用 Coding Agent 预算执行器。真实 agent 的 `hmz exec` 仍因 Windows 外部隔离阻碍不能放行。新 Codex 实验日志与状态也须留在项目；若隔离身份需重新登录由用户完成本机浏览器认证，不擅自复制全局 auth.json。

WSL2 已获批准：系统组件安装成功，当前等待手动重启；固定 Ubuntu 镜像已下载。重启后由代理先复查状态，再运行：

```powershell
pwsh -NoProfile -File scripts/install_wsl_distribution.ps1
```

脚本在 Windows 尚未重启时返回 exit 75 / `BLOCKED_RESTART`，不启动安装；目标严格限制为 `.local-workbench/wsl/EnhancedHumanizer-P0`，不覆盖已有不明目录。注册成功后仍须 Linux 工具链、隔离与真实 demo 验收。微软系统组件使用 C 盘是已批准例外；不自动重启、删除 VHD 或复制 Windows 全局认证目录。

Conda 保留给 P6 按实例预建固定科学环境，使用项目内 prefix 与 cache；当前没有修改任何已有环境。已能发现 CuPy GPU 不等于全部科学 Benchmark 依赖已安装。
# 重启后 Linux 入口（2026-10-10）

项目发行版 EnhancedHumanizer-P0 的 VHD 位于 `.local-workbench/wsl/EnhancedHumanizer-P0`。Windows 入口使用 `scripts/wsl_project.py`，无 Windows 认证变量转发；Linux 环境为 `/opt/workbench/.venv-linux`，固定 native Ubuntu Python 3.12.3。不要直接使用缺 pidfd 的旧 `/opt/workbench/.venv`。

`scripts/install_linux_tools.py` 校验官方 uv/Codex 归档和 Python 二进制，安装 Linux 哈希依赖；`audit_linux_fence.py` 在 Linux 环境执行实际合成拒绝测试。`run_p0_coding_demo.py` 是真实收费额度相关入口，会在持久 P0 ledger 中预占一个订阅回合并用 Linux timeout 控制进程组，不能在 CI 中运行。登录为 CODEX_HOME 下单独完成的 ChatGPT 登录，禁止复制宿主 auth 目录。

完整已执行结果和边界：[P0 Linux 验收](audits/P0-Linux-2026-10-10.md)。后面的 Windows 安装记录保留供审计。

