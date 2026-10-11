# 来源与本地预览交付说明

Enhanced_Humanizer 的项目许可证尚待产品所有者决定，本地预览包不表示已批准外部发布。首次发布前复核项目名称和许可安排。

本项目复用以下上游接口和运行时，未开发替代 Coding Harness：

| 上游 | 固定版本/来源 | 原许可记录 | 本地源码包内容 |
|---|---|---|---|
| Humanfia Humanize | `0488ca796c44e16b0b30468e673f541d358b07a9`；hmz `0.1.0b2` | Apache-2.0；原 LICENSE 保留于独立上游检出 | 本项目薄 Flow/SDK 适配；不含上游库 |
| DeepSeek Harness | `d743267388641bc76f17c45ce8b4c231aed1d32c` | MIT；原 LICENSE 与 THIRD_PARTY_NOTICES 保留于上游检出 | 本项目计量/任务适配；不含 Harness |
| OpenAI Codex | CLI `0.162.0-alpha.2`，可执行 SHA 见 `docs/upstreams.md` | Apache-2.0，工具独立安装 | 本项目调用适配；不含 CLI 或账号 |
| LLM-as-a-Verifier | `90e8fc215606447d6d31e9e24bff7200fb0c0994` | MIT；原 LICENSE 保留于上游检出 | 原算法的客户端注入适配；不含上游源码 |
| PyYAML | `6.0.3`，hash 固定 Windows lock | MIT；已安装分发的 `pyyaml-6.0.3.dist-info/licenses/LICENSE` 保留于私有 venv | 只含依赖锁，不含 wheel |

来源、Fork、许可证元数据和安装包清单详见 `docs/upstreams.md`、`configs/upstreams.lock.json`、`configs/installed-packages-p0.json`。此表为来源记录，不将元数据审计冒充完整再分发许可审查。Ubuntu/Conda/bubblewrap/基准仓库及其环境保持在私有运行目录，不进入该源码 ZIP。Jev 示例未复制或嵌入，地区阻塞没有以其他身份替换。

包中两份 v0.4 基线为用户明确批准在本项目保留的需求文档，原 SHA 不变。实验参考补丁、隐藏验收原始材料、科研数据、模型轨迹及登录文件均不在源码包中。
