# P6 准备交付：基准身份、环境、验收和报告接口

状态：`PARTIAL_PREPARATION_VERIFIED_REAL_BENCHMARK_NOT_RUN`。P6 已授权启动，完整 P6 尚未验收；P7 原合同无定义，范围待确认。GitHub 操作仍暂缓。

冻结配置为 `configs/benchmark-p6-v2.json`，SHA256（canonical manifest）`13314498f66d1dc37b3175d328e1dc14520e446a073b628073b30fbbfaf02955`。保留 v1 历史版，修订原因见 ADR-0012。公开材料来自 [BugsInPy](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd) 和 [SWE-Lite 官方数据](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/tree/6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2)，原始材料只存私有目录。6 Black bug ID 1..6、Requests/pytest/SymPy各2实例的真实 base SHA 已固定，4个科研槽位仍缺材料。官方 [SWE-Lite](https://www.swebench.com/lite.html) 的完整测试集有300实例，本选择的6个不是全量官方成绩。

准备脚本：`p6_acquire.py` 读取固定官方版本；`p6_freeze.py` 在已有私有材料上冻结、拒绝变更覆盖；`p6_prepare_linux.py` 建非 root Conda 环境、独立 shallow 源码及参考副本、封存依赖；`p6_evaluate_linux.py` 复用 Humanize Fence 验证正负对照；`p6_report.py` 生成 CSV/JSON/延迟、实付成本、完成率图。当前96个A–F单元全部 NOT_RUN，生成图明确说明缺值，不伪造性能。

Black smoke `BIP-black-2`：Python3.8.3、基础SHA `c8ca6b2b9ff3510bee12129824cebfc2fc51e5b2`，官方参考修复独立隔离保存。一次指定 unittest 在错误基线 FAIL、参考修复 PASS，实际探针 uid1000/CapEff0/独立PID/参考与凭据读取拒绝/环境写入拒绝。环境封条 SHA `94f81aadf796868ade25118765dcbcb796a21573f141014621fe5079ceca76d1`，6718个文件/链接项。可重复准备入口再次运行后仍保持封条相同，环境准备验证不等于模型 smoke 成功。

Miniforge bootstrap测量42.366881901秒，原定Python环境创建95.474340956秒，运行依赖安装13.028232098秒；后续补齐原声明 typing-extensions、标准包生成的版本模块及测试导入所需 MIME 表的记录均保留。早期符号链接/探针/导入失败、最终正负对照和独立复跑分别保存，不把准备失败计入参评模型任务。全过程模型实验请求0、实验API现金0，主实施 Agent 的订阅消耗unavailable。

Windows 与 WSL 确认 NVIDIA RTX4060 Laptop GPU、驱动616.64，WSL报告8188MiB；尚未安装或验证CuPy/CUDA科研任务协议。全部环境、缓存、数据和日志位于项目D盘内的WSL VHD；没有新的C盘环境或管理员变更。

验收记录、完整准备日志、依赖封条及空结果报告留在 `.local-workbench/benchmark/` 和 `.local-workbench/audits/p6-*`，避免泄漏参考补丁/研究原文。公共追踪保留86需求ID，待预算/材料/真实链完成再更新完整阶段门禁。

未完成事项：第二项 Requests smoke 的固定HTTP测试服务/全部119验收映射；针对完整仓库的有界交接、原生A/D与E/F适配和各臂统一时间/账本；两项真实smoke后12公共实例、J0/J1/J3及Merge（全失败池），J2明确地区阻塞；四项科研合同/金标准/容差/GPU协议；等时间/等现金与逐任务结论。现有P1–P5合成任务结果不得冒充这些公共基准结果。

下一步先完成第二项环境和原生执行适配，在新的P6预算获准后运行两项真实smoke；按实测申请主集预算。科研材料到齐后冻结新合同。P7若由用户确认为安装打包/交付准备，需要另立范围和验收，首次外部发布前复核项目名，发布/产品PR仍需人工批准。

离线验证：Windows62测试（60 PASS、2平台skip）；native P6八项全部PASS（包含Windows跳过的真实内部/越界链接检查）。P1/P2/P3/P5账本SHA与阶段末保存值逐一相同。Gitleaks及最终源码提交/备份以私有p6-delivery-local.json为准；未声称远程CI已运行。
