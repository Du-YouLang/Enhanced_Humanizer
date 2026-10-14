# Pi GRANGER 冻结源码复核

后续用户授权的三项定向核验已完成，最新补充回执`0ec0442f`：冻结范围7 PASS/1源码FAIL，原数值/候选/结果不覆盖。两个solve疑点各经18组输入、11组真实后端错误传播核验排除；另各一组小ridge压力精度失败独立记录。P3/DS的缺少跨warp同步由原CUDA的PTX和索引映射确认，源码门FAIL，不冒充动态数值失败。此后续共72次小输入调用、模型0、整题重放0；下文零候选执行/5 PASS/3待定是较早快照。详见[ADR-0036](../decisions/ADR-0036.md)和[P6分析审计](P6-analysis-2026-10-14.md)。

2026-10-14 18:00（北京时间），8份原始冻结源码均已逐份阅读。补充结论为5 PASS、3 INDETERMINATE；8份原数值检查仍全部通过。此处只完成明确列出的源码门与原数值回执合并，不宣称完整P6/Pi科学验收。

原16格矩阵回执`36ac854f8de91d3c2d9cbc70c4bd256a375fb11d344f4e6600607e5d55549985`、原结果行、候选及选择保持不变。新补充回执为`formal-source-review-20261014T095944Z`，SHA256 `c1056714e62a7d539f5586f858fdc43ad16e881012cf5668d12eb4e034aa7b8a`。每份源码经原candidate/program摘要、冻结提交的Git blob、干净工作区和隐藏检查前冻结时间独立绑定；Git读取仍经过原OS fence，没有在边界外执行候选Git配置。

| Profile | DeepSeek | 独立ChatGPT订阅 | 尚未消除的疑点 |
|---|---|---|---|
| P0 原生Pi | INDETERMINATE | PASS | DS的`cp.linalg.solve`未显式启用错误状态检查 |
| P1 Scientific Skills | PASS | PASS | 无本轮阻塞项 |
| P2 NeuroForge | INDETERMINATE | PASS | DS的两次`cp.linalg.solve`未显式启用错误状态检查 |
| P3 Research Loop | INDETERMINATE | PASS | DS共享内存写入与复制之间缺少同步 |

P0/DS源码SHA256 `fdd38d103ecde27295b89ab30f7781d790e4a4731302f342e8fe259dc59ae552`第187行、P2/DS `1d1e92061e83297b964873ec7f2597234a5d79fb5fe15e500afe5d7e7379dfed`第208/214行使用默认线性代数错误配置。末端有限值检查不等于检查求解器状态。冻结任务本就要求求解失败传播异常；现有样本没有观察到错误数值，不把未验证的异常路径改写成实测FAIL。原安装CuPy14.1.1的`_solve.py`、`_util.py`和`cupyx/_ufunc_config.py`已只读留存并校验摘要，默认配置为ignore；与[CuPy官方solve文档](https://docs.cupy.dev/en/stable/reference/generated/cupy.linalg.solve.html)的告警一致。后续应独立核验失败状态传播，不能修改原候选后将新结果混入本轮。

P3/DS源码SHA256 `9be645e2d0967244687acf8c0672f8c300a0b679d937f8b16e3c0e0109d8d8b9`第162行写共享Gram对角线，第163–166行复制restricted子矩阵，中间没有块级同步。lag=8时，线程4写`sG[68]`，另一warp的线程36读取同一位置；第172行的barrier发生在读取之后，不能建立此前写入到读取的先后关系。这是结合源码与[NVIDIA同步规则](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-c-programming-guide/index.html#synchronization-functions)得出的静态疑点，未执行候选或复跑数值来验证实际触发频率。保持INDETERMINATE，不将其冒充已观测的数值失败、供应商过载或普通模型超时。

5份PASS均完成原六项源码检查：实质GPU回归、无信号/回归数组下载、无假kernel或答案查表、冻结target/ridge/RSS公式、仅元数据在主机处理、无guard monkeypatch。P1/DS使用带失败标记的GPU小矩阵消元；订阅P0/P1/P2使用显式错误传播的GPU solve，P3使用GPU消元与异常哨兵。GPU残差、自然对数、精度/顺序/短窗口边界与公开CPU规范逐项核对；订阅的实现说明也已阅读。原27个数值case、10个重复/传输输出及性能测量全部复用，没有重新运行。

补充检查调用原`finalize_gc_review`及严格摘要/行号验证，只对5项证据充分的结果形成另存的PASS。3项未决记录不会通过完整源码门。新审计控制代码存于自己的内容寻址目录，没有覆盖原生冻结59份文件。原v1绑定助手因Git辅助函数裁剪末尾空白而停止、v1注册助手因冻结源码目录没有补充adjudication模块而停止；均为零模型的审计准备失败，原日志保留，v2分别通过精确diff/单独固定模块完成核验。

本次模型调用0、候选执行0、数值重放0、原结果覆盖0。累计账本SHA256 `b54271dd41f41f0da1f91c5dce65d9f690468f41f5e24eccb5def303bc28e145`前后相同：6042次DeepSeek请求、198次订阅预留、API保守上界USD108.4555581；实际扣款不可见。当前30秒v10监控继续核对原运行/恢复回执；本补充源码结论单独读取，不能只看原矩阵的8个INDETERMINATE。GitHub与外部发布继续暂缓。

Windows私有证据为`.local-workbench/audits/pi-gc-source-intake-v2-20261014.json`、`pi-gc-source-bind-v2-20261014.private.json`、`pi-gc-source-reviews-20261014.private.json`和`pi-gc-register-review-v2-20261014.private.json`。后者记录原生回执路径及摘要；这些文件不进入安装包或公开仓库。
