# Pi 剩余85格：累计USD250续行

范围见[ADR-0045](../decisions/ADR-0045.md)。用户明确允许剩余85未开始格使用既有USD250余额，旧27格及单格补跑1FAIL保持，不重放。

实际于北京时间14:33:46启动`formal-full-compare-20261015T063346Z`，续行v4 plan9d7b3bc254d74f0aa5871aad4f7402cb7f3cd61f3e56088a81ced7292ff3f902；包装器continue-unstarted-bed8f772553885ee调用新内容寻址controller-full-3af2cb0ab220b593。原生PID364/boot e2b09f44-756c-4bf3-8238-395a040fca8e/startticks1862367/command afe0b274cfbb4c82a63cd2a60b2600987b69a37bc856fa737869030f0cf579d4在启动和独立状态核验吻合。首格Black-5/P3/DeepSeek，14:34快照0/85新格、累计27/112，处于真实模型执行而非准备。

同锁预算范围修订：oldledger f4bc02e4封存，6980DS/210订阅/USD201.0724632保守上界和原未知预留全保留；只改授权范围/摘要，累计USD250/10000不变，新ledger059cce0a。新paid scope只允许原112有序清单[27:]，包括对应DeepSeek与订阅；原失败/完成/不确定格、单格再跑或额外任务均被拒绝。余额USD48.9275368不能保证完成85格。开始后14:34:28独立快照6991DS/210订阅/USD201.7260969上界；实付unavailable。所有在途、重试和未知usage继续累计，不能重置或退款。

实际控制：`formal-full-controls-20261015T062632Z/receipt.json`，SHAaf11a6db01404b2280c6c7bf27cb462f345997a1c5b71c24b9ffb0a3ab6383a6，14题环境/SDK/工具/网络控制PASS、模型0。续行正控验证四批有序回执、334份证据pin（包含单格补跑与single-use marker）、源/环境/预算和旧账本前缀。实际四负控分别更改旧格重放、缺格、保留结果摘要、源码pin，均在模型前被拒绝，ledger不变。首次prepare缺可信依赖路径而被拒绝、准备期间在full控制完成前请求续行controls被拒绝，均零模型，修正路径并等待控制完成后正控通过；旧失败现场保留。

功能精确提交c3f5cd017884485a01562b9a8daccf70c87b9db0：Windows262（9平台skip）、原生262（3平台skip）、Node10通过；精确CI38692768385的integrity/secrets/linux-budget均SUCCESS后[PR52](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/52)合并8bf59473e154af33cdb5f7880482308f525d639d，随后付费启动。旧冻结执行器未覆盖；新代码/计划保留原模型、科学阈值、时间900/1200、每角色1000/每请求600/输出256000，DS10尝试策略不变。

原watchdog现路由只读v17：配置14d8d51515445c9f84cc07fab06339bc9998fba2c8c45f3ce0149c3b89a8d3ed、inspector7bad7b3f31456ce5ca50b7c8a0e445e3789bcdc780d6b49a6ab0770a12efbc72；原v16禁用/文件和路由备份保留，30秒循环与登录/每分钟恢复保持，未强制重启测试。继承v16明确标注的历史主16题/16敏感性baseline；85/112新鲜读取及单格补跑独立1格分别保留，不能混淆分母或称原历史链全部实时复验。Luna实际只读独立核验新心跳、owner/command、预算，Sol负责代码和科学。45分钟巡检已更新新run；观察器/检查器provider调用和账本写入0。

后续结果依实际receipt追加；数值PASS仍须独立科学源码/报告/图表接受，不将已启动称全85完成或完整P6/P7验收。产品逐PR人工审核、独立发布确认不变。
