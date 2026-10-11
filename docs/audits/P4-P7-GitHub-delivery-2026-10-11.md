# P4–P7 GitHub 补交记录

用户恢复并授权 GitHub 交付后，通过本机已有代理重新核验 `Du-YouLang` 身份、同名公开仓库及管理权限；只对当前进程设置代理，没有改变仓库可见性、协作者或 main 保护规则。按阶段完成下列开发 PR；每项均在对应 head 的三个 CI 检查实际成功后合并。

| 阶段 | PR | 最终交付 head | 合并 commit | 实际通过的 CI run |
|---|---|---|---|---|
| P4 | [#12](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/12) | `8de702adf9d13d343fada7b85b317c938bf8401f` | `6e3d5f9069d86115e6c9837fb5b081aa824c8885` | [38139353194](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38139353194) |
| P5 | [#14](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/14) | `0ceadde32e306f33c2933bb7ca2db5305d7c06ee` | `93aa8ceb9d9640ae393a67e74ffa7bb327332bcb` | [38140105361](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38140105361) |
| P6 smoke | [#16](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/16) | `ef98d40c9b7ff88bd88d8ed79d6f8f676351dda5` | `c24cd522a57f88baf412cb1ca8aed30bcab18e98` | [38140551199](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38140551199) |
| P7 安装预览 | [#18](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/18) | `ef085e5abe5ca109a24bfd820138f20d252e5212` | `525adc42429da9d53d71e83e20c835c3c522772d` | [38140718635](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38140718635) |

每项检查包括 `integrity`、`secrets`、`linux-budget`。对应 Issue #11/#13/#15/#17 已关闭。所有创建的 PR 均已附到本会话。

失败也保留：P5 首次 CI 因离线辅助函数间接导入 `httpx` 而失败；修正为实际网络请求时加载传输依赖，在无第三方 site-packages 的本机环境跑通 54 项后推送复验。P6 首次 Windows CI 因 runner 工作区 junction 与内部悬空链接使用不同根路径而失败；先规范化实际存在的源码根，再做原有越界拒绝，未放宽绝对链接/外部链接规则。修复后实际 Windows/Linux CI 均通过。

这些是开发交付记录。P6 完整 16 项/96 单元主集和科学效能仍未验收；P7 仍是本地安装预览，未对外发布。历史文档中的 GitHub 暂缓是当时状态；由 ADR-0016 最新用户授权取代。产品生成的每次 PR 仍需独立真实人工审核，不能继承本次开发 PR 合并授权。
