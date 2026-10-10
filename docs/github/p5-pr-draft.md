# 本地 PR 草稿：P5 交互工作台与原生执行控制

尚未创建远程PR，等待用户恢复Du-YouLang连接。基线为P4阶段提交`8de702adf9d13d343fada7b85b317c938bf8401f`，开发分支`feature/p5-exploration-workbench`；P4先交付，本PR再指向同步后的main。关联本地Issue说明docs/issues/P5.md；远程Issue待建。

工程事件现在可以在本机探索图中查看真实提交、Diff、冻结测试和完整Harness日志。用户可设N/阶段累计预算、启动原生Humanize Flow、暂停/恢复/停止、从历史快照新分叉，并记录路线和本地PR审核提案。继续复用官方DSH/Codex；后台强制owner session/Origin/CSRF、硬测试和每个精确head的新人工审核，远程发布按用户要求禁用。

验证：Windows49 Python（1 Linux-only skip）、原生Linux42、Node预算3、三个真实DS候选独立复验、原生零模型checkpoint/权限/取消控制、8节点恢复及私有备份新目录恢复。具体SHA/测量见docs/audits/P5-2026-10-11.md、P5-evidence-2026-10-11.json。

验收边界：P5原型和控制可审阅；新的独立Sol评审/Reviewer/Builder真实链因订阅配额中断，功能阶段PARTIAL，不能以本PR/CI/merge宣称P5完成。DeepSeek30请求、API保守上界$0.1014468；Codex2预留回合，失败usage unavailable。P6未开始。目标仓库/基线/隐私/CI和真实产品人审仍需发布前预检。

回滚：保留P4/P5阶段提交与失败refs/bundles，用新分支/revert恢复；不reset或删除模型失败现场、记忆journal、私有备份。恢复实例必须使用新目录。
