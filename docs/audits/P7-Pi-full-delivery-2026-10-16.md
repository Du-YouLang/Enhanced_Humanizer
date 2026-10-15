# P6分析与新版P7本地交付验收

2026-10-16，P6完整覆盖补充分析和新版P7本地预览准备实际通过。功能源提交82163c891ce012d132197d9c7573c09b8574369a、精确CI38822591358的integrity/secrets/linux-budget均SUCCESS，PR63合并cca3ef3ed9a1c2709c051acdab8af4ded2e1033c；本地main、origin/main及GitHub API已核对一致。后续本审计文档提交独立于安装包功能版本。

| 项目 | 实际验收 |
|---|---|
| P7来源 | 502份提交文件与source.bundle共503个文件；精确功能Git提交 |
| P7包 | 2,968,233字节；SHA256 955e0c45a78669bc07cd50d1602f41a3d9bca7bdeba1415fcd62a3c003b1b022 |
| 校验 | 实际ZIP/SHA/清单通过，错误SHA拒绝 |
| 全新安装 | 独立目录与新Windows venv，哈希锁依赖和doctor通过；凭据未复制 |
| 新预览 | 127.0.0.1:8791，九组HTTP检查通过，live/model/remote均禁用 |
| 端口保护 | 同目录复用、跨目录拒绝，精确PID/创建时间/命令/用户及两服务状态保持 |
| 旧版回滚 | 原ef085/6e3d2435包重新安装到另一个新目录；8792九组HTTP检查通过；既有旧安装和服务保留 |
| 本地测试 | Windows276项（9skip）、原生精确新增报告五项；另有精确功能Linux CI通过 |
| 历史备份 | pi128-analysis-delivery-20261016.private.bundle，完整历史验证通过 |

安装包位于`.local-workbench/worktrees/p7-pi128-delivery-20261016/.local-workbench/deliveries/p7-pi128-preview/`。新安装在同一隔离工作树的`.local-workbench/installations/p7-pi128-preview/`，旧版新安装在`p7-pi128-rollback-ef085/`。所有新增环境、缓存和记录仍在项目D盘目录内；没有系统功能或全局账号变更。

P6补充报告已保存为`.local-workbench/benchmark/reports/p6-pi128-analysis-20261016-v2/report.html`及Markdown、JSON、两张科学图。独立私有压缩包`.local-workbench/benchmark/report-deliveries/Enhanced_Humanizer-P6-Pi128-analysis-20261016-v2.private.zip`含36项，SHA256为823e0c880d85eb401b397360bc628e604aa0f5e39d7742aab40676ac93f6acc1；清单、CRC、每项哈希实际验证。仅本地交付，不上传私有科研材料。Pi审核表86通过/38失败/4基础设施未决；旧A–F96为65/22/9证据未决，见完整P6分析审计。

权威验收回执为`.local-workbench/audits/p6-pi128-p7-accepted-20261016.private.json`，SHA d05548ec1fb4e6620e43fa28d246ab1ad0970bc9ffeb2aedee5370990ee1ce34；其绑定安装、两组HTTP、端口、精确CI、包、报告和全部科学补充hash。原模型/候选/数值重放均0；账本9076DS/254订阅/USD231.078648上界与bc4bc1d6不变，实际现金不可见，未知166项预留保留。

保留的管理员准备问题：后台启动命令未收尾但同一预览已健康，仅终止精确自己的审计launcher并复用原服务；端口负例首次因Windows错误流编码解码失败，改UTF8审计后两服务未变；私有报告首次ZIP清单使用Windows分隔符，原失败包保留，另存v2验证。均未重跑模型、重装新预览或改变冻结任务。

本次完成本地分析与交付准备，不是全部实验通过或完整科学普适性证明。产品许可、暂定名称和对外发布仍须人类确认；软件逐产品PR人工审核规则继续有效。完成本轮45分钟跟进后删除该巡检，保留本机30秒只读观察器及登录恢复，不自动扩大预算或重放失败任务。
