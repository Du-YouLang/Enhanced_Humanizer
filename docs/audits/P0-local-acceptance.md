# P0 本地验收记录

日期：2026-10-10（Asia/Shanghai）。实施提交 `f59af22da1173b34aa3b87f885ff851f06da6d75`；分支 `feature/p0-environment-audit`，主干根提交 `72ad614489a58e95b443271983e2bf78d414003f`。

本地已验收：86 ID/标签/来源/原文覆盖、两份原始基线精确字节 SHA256、32 项发布包 hash 锁、Humanize fake Flow/下一轮预算拒绝、无 prompt 的 DSH initialize、只读 DeepSeek /models、6 项治理回归、CI YAML 解析、staged Gitleaks（0 findings）、初始历史扫描（0 findings）、独立 commit/revert/历史 worktree 演练。

真实项目恢复检查：从 f59af22 建立项目内 detached worktree，运行 `scripts/check_repository.py`，52 个跟踪文件 / 86 ID / 原始 hash 全部 PASS，工作树干净。checkpoint tag 为 `checkpoint/p0-local-2026-10-10`，指向 f59af22。

已生成完整 Git bundle（含 main/feature/checkpoint refs）并由 `git bundle verify` 验证通过。代码检查点 bundle SHA256：`6e6f4fc8e3814d415e2ea0f4236a2adcc1e603942be0e6b0f31136fc462cab70`；文件在 ignored `.local-workbench/backups/p0-local-2026-10-10.bundle`。后续文档记录提交的最终 bundle/head 在本地 audit-session.json 追踪。

32 项已装包的版本与许可证元数据见 `configs/installed-packages-p0.json`；元数据缺失/长文本显式标注，未宣称法律兼容性审查全部完成。

**阶段判定：LOCAL_AUDIT_COMPLETE / P0_GATE_PENDING。** 尚未获得仓库可见性/Fork/权限/额外推理费用授权；未执行 GitHub create/Fork/Push/Issue/PR/CI 或任何额外模型生成；Windows OS fence、真实 Coding 工具与 Jev/LAV 端点仍未验收。没有主干合并，P1 未开始。

原始日志、负结果、扫描报告、探针耗时与最终提交引用位于 `.local-workbench/audits/`；可共享说明见 `P0-2026-10-10.md`。本聊天 Token/订阅使用不可见，记录 unavailable；额外 API 推理调用为 0、推理现金 USD 0。
