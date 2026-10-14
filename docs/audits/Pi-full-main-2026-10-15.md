# Pi 全主集补测

用户要求补全此前未运行的14题，并明确Luna监控、Sol科学核验/改代码。旧两题16格完整保留，新112格单独冻结；合计覆盖16题128格，每配置/模型/题目仅一轮。见[ADR-0040](../decisions/ADR-0040.md)。

初始账本6042次DeepSeek/198次订阅预留/USD108.4555581保守上界，实付不可见；旧16题主集96行、16次轨迹敏感性、旧Pi16行和账本b54271dd在本轮入口独立核对不变。上限仍累计10000次且USD200，无新额度。

新增入口`run_pi_full_main.py`和独立本机控制器；计划可通过版本文件冻结，拒绝重复/缺格/重排、旧16格重跑、额外重复轮次或扩大预算。完成步骤通过带摘要的落盘journal复用；不确定启动阶段阻止自动重放。只读`pi_full_status_linux.py`核对boot/PID/startticks/commandhash和账本，不能启动模型。

免费预检v1（UTC15:57）SDK四配置隔离/工具/计量与重试正负控制通过，但Black-1公开工具因`/etc/mime.types`未授权读取失败，尚无provider调用。v2（UTC15:59）修正后8题公开工具通过；Pytest-11148官方gold在旧公开缓存测试失败。已核对上游修订，补测在公开scratch副本中添加模块缓存清理，全部断言及原隐藏patch保留。两份失败清单/日志/回执原样保留；账本SHA前后均b54271dd。

v3（UTC16:04）冻结计划a04f41c42ec329a4e12ca16c1c2ebd31879995f4111f61edc56f12d401c0a869，独立controller-add321ab。实际回执`formal-full-controls-20261014T160451Z/receipt.json`为PASS_FULL_MAIN_ZERO_MODEL_CONTROLS：SDK四配置、计量正负、Research Loop工具/后台检查点、11题实际公开工具均通过，3题科研冻结环境/基线绑定通过；过载恢复/连续第五次停止/额度不重试的合成控制符合预期。账本仍逐字b54271dd。Windows248测试通过（7平台skip），Node8通过；新六项协议测试验证了缺格/重复/旧题重放拒绝、完成步骤复用、不确定启动阻止及预算上限。

正式模型进度、源码提交、原生/CI及独立科学结论以追加的实际回执为准；本准备门禁不是112格完成或科学成功证据。原P7预览验收只适用于此前精确包，不自动适用于本增量。

正式运行于北京时间2026-10-15 00:14:49启动，批次`formal-full-compare-20261014T161449Z`；原生owner376的boot/startticks/commandhash在启动与独立状态检查均吻合，第一格Black-1/P0/DeepSeek开始计量。启动后第一份实际快照6046DS/198订阅/USD109.0808166是含在途预留的保守上界，不是供应商扣款或完成格数。旧6042/198行通过原快照前缀逐项比较保护。

功能提交793d07293fd3c937e0b3865a89bd4b39c2f6ed32原生248全检查通过（3平台skip）、Windows248通过（7平台skip）、Node8通过。额外实际原隐藏合同重验：Pytest11148 goldPASS、buggyFAIL、原hidden_suite ccd7e4d6；公开缓存清理未破坏隐藏patch。GitHub [PR43](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/43)精确CI38596018852三项SUCCESS后合并1c106185c92734c6ef2a4068ebe96c6cfe29c449，main三项CI也SUCCESS；[Issue42](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/42)继续跟踪实际矩阵和分析，不提前关闭。

原30秒只读监控已迁入v11：配置3d985a751d200e46b2e53ee1f27d0df9e9914b04150da0c24c9df30e6697cbd1、inspector c450b62ff79b67ae4a436e116d9d8397a7e275bb94f1afa2e9c16aa628d19d43；继承原Windows登录/每分钟恢复watchdog，旧v10配置、状态和路由备份原样留存。实际新心跳证明同时读原运行和新Pi批次，观察器模型调用/账本写入均0；此次尚未强制重启验证下一次登录。原45分钟会话巡检恢复为`enhanced-humanizer-pi-45`，按用户要求交给Luna只读核对；Luna不改代码、不恢复模型、不判科研PASS。科学验收由Sol另存补充记录。
