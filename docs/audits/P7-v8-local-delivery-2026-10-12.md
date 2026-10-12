# P7 最新功能源码的本机安装与回滚

功能源码 `d05199bd5fc3e028c9813013b454eebcac77e7de` 的 P7-A01..A04 为 **PASS_LOCAL_PREVIEW**。它包含产品审核卡片的 Diff/测试关联、必填审核意见和提交反馈，以及主集连接与原生日志解析修复。完整 P6 尚未验收，真实产品 PR 的人类批准/上传也仍待操作。

实际源码包 `Enhanced_Humanizer-0.1.0-preview.1-d05199bd5fc3.zip`：SHA256 `35564561af9b4da1b4be3edfa8b247ca9bb9524c85f92f961512dfd5b02c47c4`，1,589,173 bytes，288 个成员。包内当前提交可达 Git bundle SHA256 `b4059bc0039a4e7c4c3170f2fa0564d52177b727430b72d4ca670e90764431c5`。此审计后续提交不冒充已安装的功能提交；精确包和回执保存在项目私有交付目录。

| Gate | 新的实际证据 | 结果 |
|---|---|---|
| P7-A01 | 干净源码构建，固定 ZIP SHA/逐成员验证、精确 Git checkout；旧源包均保留 | PASS |
| P7-A02 | 新目录 `p7-v8-preview-20261012-v1`、独立 Python 3.13.5 venv、hash 固定 PyYAML 6.0.3 的真实安装；doctor 为 LOCAL_UI_READY | PASS |
| P7-A03 | 8775 的真实 owner/匿名/Host/跨站/Origin/CSRF 检查；有效 owner 的模型启动与远程发布仍拒绝，事件/运行保持为空；同目录重用、另一目录占用端口拒绝，8772/8775 原服务健康状态未变 | PASS |
| P7-A04 | `ef085e5abe5ca109a24bfd820138f20d252e5212` 旧包在另目录/8772 并存恢复；真实 HTTP 安全/模型禁用/零事件/源码哈希检查通过 | PASS |

旧版回滚记录使用历史枚举 `DEFERRED_BY_USER`；独立检查仅接受该精确旧枚举，未修改旧源码或禁用项。它验证旧源码和界面可恢复，复用现有 Python；不声称重新安装了旧 WSL 或旧 venv。

实际 Windows 完整测试 123 项通过、7 项平台 skip；非 root 原生 Ubuntu Python 3.12.3 的 123 项全部通过；Node 8 项、治理 7 项、原基线/86 ID 完整性及 Gitleaks 通过。失败 Windows 替换测试及其修订历史均保留。安装/HTTP/回滚检查新增模型请求和远程 Git 操作均为 0。

全 refs 私有回滚 bundle 已真实验证：840,770 bytes，SHA256 `381219ba4af32786576341206b340d34ad8cac42bca3638edd40c70ce124c827`，覆盖功能 HEAD 和失败 refs。它是本机备份，不能当作公开发行包；源码 ZIP 继续排除凭据、科研原文/私有参考、模型轨迹和运行环境。

开发 PR #25–#28 在各自精确 head 的 integrity/secrets/linux-budget CI 均实际成功；仍为 OPEN，以便保留产品审核提案绑定的 main 基线。开发 CI 不代替每次产品 PR 的真实人工审核。外部发布仍须用户确认项目名称、许可、平台和内容。

私有证据：`deliveries/p7-v8-preview-20261012-v1/receipt.json`、`audits/p7-v8-http.private.json`、`audits/p7-v8-port-ownership.private.json`、`audits/p7-v6-old-rollback-http.private.json`、`audits/p6-p7-v8-backup.private.json`；均位于 `.local-workbench/`。
