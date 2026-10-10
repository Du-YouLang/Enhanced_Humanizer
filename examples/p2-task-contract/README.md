# P2 自定义冻结任务契约

默认入口的真实 smoke 修复 weighted mean；候选引擎也支持已准备好的独立任务或空项目。先由可信开发者在项目 WSL `/opt/workbench/source/` 下准备干净 Git 基线和固定环境，不能让参评代理安装依赖。复制 `task-contract.example.json` 到项目私有目录，替换 base 路径、精确 SHA、环境 hash 和验收程序，再运行：

```powershell
.venv/Scripts/python.exe scripts/run_p2_experiment.py pool --n 3 --concurrency 3 --task-contract .local-workbench/tasks/my-task.json
```

`prompt` 是完整工程任务，建议要求检查文件、实际编辑、执行测试及新 commit。`visible_test_program` / `acceptance_test_program` 由控制器在只读、禁网、无认证状态的候选环境运行 Python；退出 0 表示该套验收通过，必须有真实断言。两者不放入候选可写的控制器目录。`protected_files` 存基线 UTF-8 文本文件的 SHA256，最终改动即失败；从空项目开始时可以为空。`source_file` 是候选中的相对路径，可以在实现后才出现。环境 hash 使用现有 `configs/requirements-p1-linux.lock` 的 SHA256；其他冻结环境需另行配置/验收，不能任意改 hash 冒充相同环境。

入口复核 P1 Gate 和 P2 专项授权，所有候选、Judge 和重试共享阶段账本，并有候选独立限额。自定义任务的研究材料与结果默认留在私有目录，公开导出器拒绝自定义真实任务；需要公开时另做数据/许可审阅。模型失败、超时和基础设施失败分别记录；不会自动把最佳失败者当成功，也不会自动合并产品 PR。

示例 JSON 是模板，零 SHA/准备目录占位不能直接用于真实运行。空项目契约链路另有明确标记的离线 fixture 验证，未将其算入 13 个真实模型候选。
