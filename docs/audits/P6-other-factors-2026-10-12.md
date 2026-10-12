# 除输出Token以外的benchmark因素

本轮只读审计活动v11的已完成角色及历史证据，不重跑失败模型，不修改活动源码/清单/预算。区分已证实和待检查，不能把所有失败统称模型能力差。

| 因素 | 证据/状态 | 影响及下一步 |
|---|---|---|
| 单角色请求轮次 | 新Black-2 native-ds 100次、659.806秒，pool-B 100次、682.850秒；broker_denials精确Role request cap exhausted，controller为BUDGET_EXHAUSTED/MAIN_ROLE_REQUEST_CAP | 两者在900秒前停止；不是Token截断或API余额不足。100轮限制确实影响结果，需另版决定，不在活动v11中暗改 |
| 单请求总时间 | broker asyncio.timeout总120秒，独立于256000输出上限和900/1200角色上限 | 长推理或长流式输出可能在120秒停止；尚未建立本轮请求超时频率，不声称它解释了全部失败 |
| 测试与网络隔离 | native-ds轨迹100个tool调用：86bash/5edit/4read/3job_output/1write/1glob；84/94步骤共13个PermissionError，涉及sock_connect及test_blackd_request_syntax_error | 部分额外HTTP服务测试在候选网络fence被拒绝，会增加调试工作；不能据此放开任意localhost。精确冻结公开测试与额外全套测试须分清 |
| 探索效率 | 86个bash命令hash各不同，不是同一命令原样100次；包括Python/文件探索及8个测试类命令（分类可重叠） | 更大输出预算不保证少轮数；当前不能称100次都是重试或无限循环。保留源码/diff/test和终止原因 |
| 上下文/压缩 | 16:44快照新请求已知最大输入133404、输出7412，wire全256000；未发现本轮压缩失败证据 | 当前已知输入远低于1M上下文，不能把这次请求门终止说成上下文耗尽；继续监测压缩/过大工具输出，不先改摘要算法 |
| 网络、账号与控制器 | 历史已确认WSL路由及旧账号usageLimitExceeded；v10控制器无最终回执退出原因不可见 | 已有TUN/独立登录/隐藏拥有者控制器修复；保留历史infra/partial，不能当模型TIMEOUT或猜退出原因 |
| 依赖、文件与判据 | 历史Windows共享索引、旧v8原测试追加歧义、PC旧oracle等已留ADR与控制 | 新v11实际预检及原文件门已通过；继续区分运行环境、公开硬门、私有数值门、科研支持门，不能降低阈值来提高通过率 |
| 成本/时延和统计 | API峰价保守上界不是账单；订阅不可强制折美元；未知provider队列、人工耗时、首次patch/test仍有缺项 | 不作纯Harness冠军或真实现金省幅结论。Pi同模型配对、顺序/资源、失败费、重复与Skill提示开销独立冻结 |

原生worker的raw INFRA_FAIL/HTTP402已由控制器依据结构化broker证据归为BUDGET_EXHAUSTED，现有主集record保留ROLE_REQUEST_CAP失败类别，不是误把402当供应商余额错误。没有覆写原worker。编码会话100次中存在工具/测试错误，与供应商API自动重试是不同概念。

16:44:11北京时间只读快照：新策略352DS请求，累计1344DS/48订阅预留/API保守上界USD22.3784307，实际cash unavailable；pool-A383.920秒、pool-C459.899秒及Reviewer117.866秒已COMPLETED，首题仍无最终整题receipt。由此只能确认部分长预算角色完成，不预写A–F通过率。私有证据.runtime-risk-and-controls日志保存原始摘要，路径在.local-workbench/pi-comparison/intake，raw轨迹继续native私有。

科研任务还要绑定实际preparation：PC运行时gpu_coding=true，不应凭早期manifest单个requires_gpu字段为Pi猜设备授权；TMS/EGL保留冻结CPU协议，GC用本地4060，数值验收期限与编码期限独立。这些控制不由Pi材料改变。

17:03更新：首题正式receipt已实际产生，SHA bd78281923e3184b32bf62760bbd1b75eeb9787b8060463569fbf6c6424f7234；B/C/D/E/F五臂独立验收PASS，A为FAIL/ROLE_REQUEST_CAP，5/6。原N3中的pool-B请求门失败继续保留，不因B/C最终通过而删除。独立完整工具轨迹敏感性批次20261012T085607Z完成，第二题Requests-1963新run20261012T090223Z运行中。累计1388DS/53订阅/API保守上界USD23.8109277，实付unavailable。该一题结果不等于完整P6接受，也不能据此把256000、时间、融合或Harness因果混为一个已证实收益。
