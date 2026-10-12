# 对照风险及处置

| 项目 | 状态/实际证据 | 处置 |
|---|---|---|
| 版本/包名漂移 | 指导书Pi1.0；实际registry/CLI1.1.0。Scientific1.7/PRL0.6.3存在 | 固定版本、npm integrity/lock、Node archive SHA；不全局升级 |
| 配置污染与读取答案 | 四profile的资源/peer/state/auth/network真实负控制PASS | 每次尝试独立HOME/agentDir/session/worktree及OSfence；不能仅依赖PI_CODING_AGENT_DIR |
| 额外工具和权限 | P1新增sci_find；P3新增12工具。Pi本身不是OS沙箱 | 明示工具差异；复用现有最小权限，P3后台还要独立验证，不放开宿主机 |
| 输出/请求/推理预算 | 合成Pi wire256000通过；真实DeepSeek低推理模式和计量尚未完成 | same-model/same-effort探针及旧累计账本gate必须通过后才开放真实行；单请求120s、单角色100次仍独立有效 |
| 隐式重试/压缩/后台 | 四组基础fixture无重试，关闭retry.enabled及provider.maxRetries；未测压缩或PRL detached运行 | 记录全部请求，验证终止/检查点/后台耗时/费用归属；不由agent_end推断结束 |
| OpenAI供应商混淆 | 项目未配置API凭据，已有的是Codex订阅 | API组blocked；不同模式另层分析，不复制OAuth或自动付费开户 |
| 科学材料/版本 | 科学四题在现有main已READY；NeuroForge实际仅mne-python入口 | 绑定既有材料、CPU/GPU设备和数值门，知识版本差异保留；不改依赖迎合Skill |
| 相同环境仍有时间偏差 | 主集DS N3并发，新增Pi应先串行，准备时有短暂免费控制进程 | 主集原样保存；正式配对重新冻结执行顺序与资源，不能混称旧样本完全相同 |
| 文件/测试口径 | 旧v8追加原测试的歧义曾触发拒绝；v11有原文件保护；额外blackd网络测试可被fence拒绝 | 同公开合同、新文件回归规则；另记环境拒绝，绝不反馈隐藏答案或开放任意localhost |
| 统计/费用缺字段 | 单任务最佳种子、忽略失败费、把订阅转美元均会误导 | 保留全量task×profile×provider×重复、任务级配对及ITT/infra双口径；unknown留null |

首轮预选Black-2/GC共两题；任何材料、环境、provider身份或完整工具链未通过门的行不进入正式比较。256个完整Agent运行不是默认执行规模。额外NEURO-MNE/LONG-RUN诊断不并入16题主分。
