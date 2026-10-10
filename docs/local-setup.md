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

Conda 保留给 P6 按实例预建固定科学环境，使用项目内 prefix 与 cache；当前没有修改任何已有环境。已能发现 CuPy GPU 不等于全部科学 Benchmark 依赖已安装。
