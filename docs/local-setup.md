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

## P1 入口与无模型验收

P1 已完成五个真实实验，结果见 [P1 验收](audits/P1-2026-10-10.md)。P1 Linux lock 为 `configs/requirements-p1-linux.lock`，36 项 wheel；在现有 native Linux venv 内用项目 uv 的 `pip sync --require-hashes --no-build` 安装，不重建登录或删除旧环境。`configs/requirements-p1.in` 只增加 httpx 0.28.1（BSD-3-Clause）及传递依赖，安装约束保留 P0 版本。

真实运行入口为 Windows `.venv\Scripts\python.exe scripts/run_p1_experiment.py <native|humanize|rlar|flame|relay>`。它会消耗剩余 P1 预算，要求 P0 PASS/用户 P1 授权，并调用 Linux 持久 ledger；不能用直接 hmz 调用代替预算 gate。当前账本已用 30 DS 请求和 3 Codex 回合，不要重置或重复运行冒充首次实验。API Key 从已有本机 DSH ref 读入内存；不在命令行、文件或日志中写 Key。

不调用模型的检查：

```powershell
.\.venv\Scripts\python.exe scripts/check_repository.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s examples/p1-relay/after-sol -v
```

在 Windows 项目 Python 导入 `scripts/wsl_project.py` 后，`run(['python','/opt/workbench/source/verify_p1_results_linux.py'])` 复验保存的五个独立仓库；模型调用 0。`audit_p1_controls_linux.py` 与 `audit_p1_transport_linux.py` 分别是无付费控制/模拟传输检查，不能作为真实模型结果。外部测试同样执行候选代码，P1 已用 Humanize 只读/禁网 fence 收紧并追加复验。


## P2入口与无模型复验

P2使用现有36包P1 Linux lock，没有新增依赖或重建认证。真实入口（会消耗剩余独立P2额度）：

```powershell
.venv/Scripts/python.exe scripts/run_p2_experiment.py pool --n 3 --concurrency 3
.venv/Scripts/python.exe scripts/run_p2_experiment.py judge --pool-path /opt/workbench/runs/<实际P2运行>/frozen-pool.json
```

当前已用87/100 DS请求、2/6 Codex评分预留回合；不为重复演示清零或退款。J2无凭据，不能借用DS预算购买Jev。自定义任务见 examples/p2-task-contract/README.md，科研材料默认私有。`deploy`只复制固定公共源码，无模型调用。

无模型复验：在项目Python导入wsl_project.run后调用 `/opt/workbench/source/verify_p2_results_linux.py`，独立重测13个真实commit并追加受控故障/超时证据；`audit_p2_custom_contract_linux.py`验证空项目契约和已证明LAV缓存重放，均不请求模型、不改变真实ledger。重跑会生成新的私有故障fixtures，不删除旧记录；正常验收无需重复产生。Linux单测部署为平铺source时设置PYTHONPATH=/opt/workbench/source，CI仓库目录不需要该适配。
