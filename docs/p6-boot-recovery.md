# 本机 P6 重启恢复

恢复服务在 Windows 当前用户登录后启动，无需打开 Codex。WSL 与科研计算仍在本机。当前冻结 benchmark 正常运行时，服务只读取进度，不停止、不重新部署、不启动第二批。

重启后核验完整回执，已完成题及完整工具轨迹评分不会再次调用模型；如果 execute 完成而 sensitivity 尚未开始，仅补 sensitivity。被断电打断或启动状态不明的题保留 pending，自动推进其它尚未开始题。模型流、未提交代码和训练中间状态没有统一可验证的恢复接口，因此不能保证中断题原位恢复，也不会伪造其结果。这一限制在恢复状态和最终 benchmark 覆盖率中显示。

累计主账本不重置，未知费用不退款。恢复服务自己的事件、启动意图、进程归属和状态保存在项目 `.local-workbench/recovery/`，旧批次索引和运行目录只读。发现预算上限、源码变化、账本损坏、未知进程或记录损坏时停止新增模型调用并写明阻碍。

运行入口：`p6_boot_recovery.py supervise --config CONFIG --execute`；`--once` 做单次检查，不在原控制器存活或同一次 boot 中触发新模型。安装器 `install_p6_boot_recovery.ps1 -ConfigPath CONFIG -Mode Status` 查询系统启动注册；`-Mode Disable` 移除／禁用启动注册并关闭恢复 marker，不杀当前 benchmark。

这是本轮实验专用服务，只覆盖绑定的原批次、manifest 和账本，不自动选择未来实验、另一个账号、另一预算或产品 PR，不代替外部发布与 PR 人工审核。
