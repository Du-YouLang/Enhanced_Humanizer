# P0 外部隔离方案与安装状态

状态：用户已接受空间方案并授权安装。WSL 3.0.1 系统组件安装成功，虚拟机平台已启用，Windows 要求手动重启；Ubuntu 镜像已下载校验但尚未注册。未自动重启。P0 的真实 Humanize Coding demo 保持未通过，见 [安装记录](audits/P0-WSL-2026-10-10.md) 和 ADR-0005。

## 实测依据

本机 Windows 的 Humanize 0.1.0b2：`enforceable(net=False)` 和 `enforceable(net=True)` 均 false；DSH 驱动只支持 bypass，须由外部 fence 执行限制。Windows CLI/SDK 可以加载并不代表能安全执行 Coding Flow。独立 API 文本探针没有工具权限，不能替代这个验收。

## 建议：项目专用 WSL2 + Ubuntu 24.04

- 为 WSL2 启用 Windows 虚拟机平台/必要子系统并安装微软稳定版 WSL。系统组件、内核服务和 Windows 自身管理文件由 Windows 放系统盘，这是“新增环境全在项目目录”需要用户明确批准的系统例外；发行版不采用默认 Store 目录。
- 发行版注册名拟为 `EnhancedHumanizer-P0`，虚拟磁盘、下载包、备份放 `D:\Desktop\Enhanced_Humanizer\.local-workbench\wsl\`。使用官方支持的安装位置或 import 路径；若实际 CLI 不支持目标位置，先停止核查，不静默安装到默认用户目录。
- Linux 项目、环境、运行日志和缓存放这个发行版自己的 ext4 文件系统，物理承载仍在上述 D 盘项目虚拟磁盘。先不修改已有 Windows/Conda/Python 环境，不新增 Docker，不向 Linux 复制整份宿主认证目录。
- 空间规划为 D 盘预留 20 GiB、C 盘系统组件预留 4 GiB，属于工程预算，非下载包精确体积；2026-10-10 实测 D 剩余约 131.08 GiB、C 约 48.44 GiB。超出预算先报告，不自动扩容或清盘。
- 可能需要管理员 UAC、BIOS 虚拟化或重启。自动安装不替用户点击 UAC，不自动重启；需要时由用户操作，重启后继续同一个 P0。
- 安装后先探测 Linux kernel、Landlock ABI、seccomp 与 PID/网络能力，再做工作树外写入、相邻候选读取、宿主凭据访问、主干 refs 和危险 Git 操作拒绝测试。WSL2 本身不是验收通过；拒绝测试通过后才运行实际 hmz demo。
- 模型访问仍使用已批准的 P0 剩余额度；Linux Codex 如不能复用现有订阅，需要用户在本机浏览器登录，不要求在聊天发送认证信息。

暂停/回退：先停止该专用发行版，保留 VHD/导出备份；不自动 unregister、删除虚拟磁盘或关闭既有系统功能。确需删除/卸载时再按明确目标取得授权。

依据：[微软 WSL 安装](https://learn.microsoft.com/en-us/windows/wsl/install)、[基本命令与 import/export](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)。实际安装包版本、校验值与命令结果须在执行时留存。

## GitHub main 保护方案（独立授权）

用户最新决定：开发仓库不施加过多 PR 限制，以本地/GitHub 同步为重点；采用 ADR-0004 的轻量 PR/CI 流程。以下 JSON 提案保留为历史参考，**不应用**。产品自身每一次 PR 的人工审核仍须严格实现。

原请求体为 `configs/github-main-protection.proposed.json`：main 更新须通过 PR，最新 base/head 的 integrity/secrets 两项 GitHub Actions 成功，禁止 force-push/删除，规则适用于管理员，要求对话解决。不增加协作者或账号 scopes，不收费升级。

## 存储实测与估算

2026-10-10 15:56 +08 实测目录文件逻辑长度：`.venv` 0.269 GiB（约 276 MiB）、独立 Python 0.059 GiB、缓存 0.322 GiB、三个上游源码 0.713 GiB、扫描工具 0.029 GiB，连同 Git/备份合计约 1.39 GiB。uv 硬链接可能重复计数，不能把该总和冒充 NTFS 物理分配大小；测量耗时 1.526 秒，明细在 ignored audits/storage-followup.json。

Ubuntu VHD 尚未建立，不能实测最终环境占用；已下载的两个官方安装文件合计约 0.705 GiB。P0 Ubuntu + Git/Python/Node/Humanize/DSH/Codex 的新增容量工程估计为 5–10 GiB；建议留出 15–20 GiB 余量，C 盘系统组件暂按 4 GiB 预留。不是立即预分配这些容量。微软说明 WSL2 VHD 会按使用增长，虚拟容量上限也不等于当前物理占用，见 [WSL 磁盘说明](https://learn.microsoft.com/en-us/windows/wsl/disk-space)。后续 P6 的科学依赖/数据/镜像另行测量和规划。

原保护提案中的独立 reviewer 数为 0，因为当前只有一个账号且 PR 作者不能自我批准；这不是已应用设置。开发仓库遵循 ADR-0004 的轻量 PR/CI；产品自身每次 PR 的真实人工审核另行实现，不能混同。
