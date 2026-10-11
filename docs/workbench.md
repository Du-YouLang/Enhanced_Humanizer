# 本地工程记忆与工作台

P5 界面在项目根目录启动：

```powershell
.\scripts\start_workbench.ps1
```

在本机浏览器直接打开 `http://127.0.0.1:8765`。只监听 Windows loopback，不能作为多人服务器部署。页面读取真实工程事件；左边选任务，中央拖动/缩放并点击节点，右边展开提交、Diff、冻结测试、完整原生日志和事件历史。历史来源节点可跳回原任务；人工注释、拒绝路线、更新路线、分叉与待审 PR 提案也会进入图。

底部选择 N=1/3/4/5、明确的 J0/J1/J3、候选/运行时限、Sol 构建方向。任务合同和 P5 累计预算在可展开区域；默认是已冻结的加权均值合成演示，不能作为科研效果证据。更换科研任务需要明确 Linux 基线/commit、可见与隐藏验收、保护文件及固定环境；完整 JSON 合同经后端验证。Jev 地区阻塞，不能将 Sol 标为 Jev。

“启动新任务”运行原生 Humanize Flow：DS 候选→独立评分→Reviewer→M 硬复验→比较→Sol Builder→独立复核。暂停在下一角色边界完成持久 checkpoint，当前有界调用可能先结束；“恢复”继续同一原生 epic，已完成阶段不重放。停止会收束当前原生进程并保留代码/日志，程序快照不代表模型成功。服务重启会将未结束任务标为 INTERRUPTED，不自动重新花费额度。

从所选历史节点继续会建立新分支、保留原 SHA，再转入隔离 Linux 执行。被拒绝的路线须先更新方向；“更新路线”同时将理由填入下一轮 Sol 构建方向。若只是临时服务失败且完整冻结候选池可读，使用“重用候选池重试”：保留 N/合同/原候选证据，另开新任务和独立评审，候选生成新增调用为0；后续角色仍消耗真实订阅或 API 额度。N 改变须新生成。不会自动重试、换模型、充值或重置账本。

P5 操作上限 $5 /160 DS请求 /16 Codex预留回合，可在界面下调，按整个阶段累计；每请求≤120秒、候选/角色≤600秒、累计活动运行≤1200秒。Token 的普通 input、cache read、cache creation、output 分开记录；未知为 unavailable，不回收未知现金预留。API现金保守上界与不可见账单/订阅美元成本分开。

“准备 PR 审核”目前仅产生本地、精确 head/硬测试/证据绑定的提案。每个实际产品 PR 都需要新的人工审核；未通过硬测试、提交或证据变化、过期/已消费均拒绝。用户暂缓远程操作期间发布后端硬拒绝；目标仓库和基线仍为 unassigned，不能将合成演示代码直接推到工作台主干。不要把开发 PR 或测试 fixture 的批准当作真实用户批准。

2026-10-11 当前：P5 新执行链已完成真实 J3→Reviewer/M→独立比较→Sol Builder→最终J3，并在隔离环境独立复验通过；Reviewer后真实暂停/分叉/恢复也已验证。历史订阅限额、协议失败及失败工作区保留，实际产品PR仍待人工审阅且远程发布暂缓。见 [P5 报告](audits/P5-2026-10-11.md)。

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

新备份会记下导出时的精确仓库分支/HEAD，并在恢复后检出该版本（包括尚未合并的本地阶段分支）；旧P4备份仍可读。Git备份不包含未提交文件，manifest明确记录working_tree_dirty与uncommitted_files_included；模型部分工作须先保存程序快照，开发源码须先提交或另行本地保存。不要把“导出成功”当作所有脏文件均已备份。
