# 本地工程记忆与工作台

在项目根目录使用现有 Python：

```powershell
python -B scripts/workbench.py import-p3
python -B scripts/workbench.py verify
python -B scripts/workbench.py list
python -B scripts/workbench.py fork --node <保存的节点ID> --reason "新的探索方向"
python -B scripts/workbench.py handoff --node <节点ID> --reason "下一步任务"
python -B scripts/workbench.py revert --node <节点ID> --sha <精确commit> --reason "撤销此变更"
python -B scripts/workbench.py export
python -B scripts/workbench.py restore --archive <本地ZIP> --destination <项目内新目录>
```

默认私有状态在 `.local-workbench/workbench`。`events.ndjson` 保存完整历史；`index.sqlite3` 可用 `rebuild` 重建；`artifacts/` 包含完整日志与证据，按人类/代理访问级别控制。不要上传整个目录。Git worktree 用于恢复/查看，模型执行继续使用隔离 Linux 环境。CLI 不会在 Windows 运行候选代码。

备份是工程记忆和 Git 数据备份，不含登录凭据或 WSL OS。恢复不覆盖现有目录，不删除失败 worktree。原始 baseline/运行依赖仍由 lock 和 WSL 文档管理。事件损坏时保留原件，恢复经过校验的备份；禁止用“清空数据库”掩盖坏事件。

节点类型和实际执行状态分别保存：测试通过的预算停止候选仍是 `BUDGET_EXHAUSTED`；程序保存的部分工作不冒充模型提交。开发 PR #10 是开发交付记录，不能用作产品 PR 的人工批准。
