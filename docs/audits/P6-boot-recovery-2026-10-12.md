# P6 本机重启恢复验收

用户明确要求续跑、开机自动恢复、已完成题不重跑、日志与预算累计，并不干扰活动 benchmark。实现独立 supervisor，沿用 v12-final2 `b751822058b84512f8755676881e38eb691081ae8fa58456737824803bffc454` 以及原累计 MainLedger；冻结入口、runtime、manifest、原批次索引均未改。见 ADR-0028。

26 项零 provider 控制通过：已完成（包含失败分支）整题跳过；只补未开始的 sensitivity；丢失 Windows controller 时观察仍存活的 native controller；原进程仍活动时禁止新增模型；新 boot 才运行尚未开始项；中断/启动不明槽位保留 pending；实际独立进程崩溃后的持久 intent、真实互斥锁/释放、hash-chain replay 和损坏尾部拒绝；累计账本前缀不可删除/改写、允许正常结算降低费用上界；timeout 父进程与 runtime 子进程识别、跨 boot PID 不可信、缺少六臂完整回执拒绝。

模拟 boot 端到端控制实际调用两个 fixture Python 子进程，只启动第二题的 execute/sensitivity，第一题两个已完成阶段调用数为零。该控制使用合成 inventory，provider 调用零，不能称为真实模型或物理断电验收。

真实安装先在项目 `.local-workbench/recovery/p6-boot-v3/`，最终修正升级到 `p6-boot-v4/`，使用当前用户 HKCU Run 单独启动值。Windows 当前 token 非提权，Task Scheduler 注册被操作系统拒绝；核验注册未成功后采用无需密码/管理员权限的用户登录启动方式。初次注册检查错误与拒绝记录保留，不称成功。实际 HKCU 值、固定 Pythonw/配置、后台进程和 heartbeat 已核验；必须登录该 Windows 用户后恢复，无需打开 Codex，不配置自动登录。

服务实际状态为 `OBSERVE_ORIGINAL`；当前 Windows 主集 controller 仍 PID30312、创建时间2026-10-12T20:54:58.373942+08:00，服务没有模型 launch intent。首次 native inventory 发现历史 offline launch 不在 matcher 中而失败关闭，未读取真实凭据或调用模型；补充 offline 排除与 GNU timeout 子进程归属控制后通过。旧准备目录 v1/v2 保留，失败原因见本轮工具记录。v4升级保留v3完整journal前缀和累计状态；恢复健康后清除旧blocked状态、单次模式只启动一阶段、锁冲突不混作其它文件PermissionError。旧版本控制仍只对其版本有效，最终源码控制/CI见独立回执。

Windows 完整测试187项（180通过、7平台skip），61.911秒；独立WSL恢复控制26项全通过，0.337秒；治理7项及staged repository/Gitleaks通过。真实恢复服务进程终止/重启（只针对精确核验过的服务PID26100→31316）后hash-chain/累计状态仍可读取，主集原PID/创建时间/命令未变、恢复launch intents仍为零；第二个服务入口实际被OS互斥锁拒绝。此服务进程测试不是对当前模型或整机实施断电。

恢复是整题／阶段边界，不具备任意模型流/训练中间状态续跑。断电中的题保留待恢复并继续其它未开始题，不把残缺题假称完成，也不会重新跑它的已完成模型角色。普通失败、网络 pending、断电 pending 分开记录；完整主集是否完成仍取实际回执。未实施真实关机、重启、断电或模拟断电到活动模型进程，避免干扰当前 benchmark。

独立安装进程重启控制、原 controller 零影响、累计 ledger 前缀、精确 commit/CI 与私有备份证据取 `.local-workbench/audits/p6-boot-recovery-accepted.private.json`。此审计不沿用旧 P7 包的验收，也不改变产品 Draft30 人合并和外部发布确认要求。
