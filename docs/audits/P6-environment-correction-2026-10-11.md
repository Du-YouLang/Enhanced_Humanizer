# P6 环境对照修正与模型入口准备

此前 P6-preparation 的 Black 负对照遗漏 `tests/data/fmtonoff4.py`。旧错误基线的 FAIL 来自缺输入文件，不能证明目标代码缺陷被验收器检测到。旧日志和提交保留；本次补齐同一个上游回归输入并重新运行：基线因格式化断言失败、参考实现通过，输入、测试程序及命令一起纳入隐藏套件哈希。这项修正发生在 P6 模型调用之前。

Requests 原生环境为 Python3.9.23/pytest7.4.4，固定 HTTPBIN0.7.0/Flask1.1.4/Werkzeug1.0.1 和完整文件封条。第一次 Flask2 环境导入失败，留为独立失败环境，未覆写封条。当前环境 SHA256 为 c58d034bf73f0f452bcb8d300d6c94b37782341b406b139ac2d83c2c0d2d0d24。

Requests 保留官方材料的 7 FAIL_TO_PASS + 112 PASS_TO_PASS 全部 119 个测试身份。当前基线只有目标重定向断言失败，参考修复 119 项全部通过；原数据另外六项 F2P 在本机环境中基线也通过，因此不声称复现其六个原失败。所有 JUnit 身份必须唯一匹配，零收集、导入故障和未映射测试不能算 PASS。

绝大部分 HTTP 测试使用同一个固定本地 HTTPBIN 进程。两项原始硬编码 `https://httpbin.org` 测试保留外部 HTTPS 依赖。旧 Requests 的 vendored urllib3 在代理下误把代理 IP 用作证书主机名；公开测试启动器只给已有 loopback proxy 添加目标名称别名，并把忽略环境代理的本地 TCP 连接通过同一个精确主机代理作 CONNECT 隧道。没有关闭 TLS 验证、修改 Requests 代码或替换测试断言。该路由只匹配 loopback fixture 的精确端口；其他直连仍被原 Humanize Fence 拒绝。证书、fixture 版本、路由源代码及实际权限探针均可复验。

这是固定本机环境的探索性比较，存在历史依赖版本与原 SWE-bench Docker 环境偏差，也包含两项外部 HTTPS 的可用性风险；不报告官方 leaderboard 分数。一次当前参考对照约 20.244 秒，无模型调用。运行每个模型实验前再次验证基线与参考实现，不向模型移交隐藏测试、参考修复、私有路径或旧会话。

A/D 通过上游 Humanize 原生 Driver 直接打开官方 DSH/Codex 单会话，不运行增强 Flow；B 的三个完整候选由 Humanize Flow 并发调度，C/E/F 使用已有 Reviewer/Judge/Builder Flows。新增代码负责测试任务适配、预算、隔离、Git 和证据，未重写 Coding Harness。每个候选/角色使用独立 Git objects、HOME 和缓存；实际执行前检查 UID、capabilities、PID namespace、环境只读、私有材料拒绝以及输入只读。当前 Black 的三类零模型权限探针通过；真实模型结果尚待运行。
