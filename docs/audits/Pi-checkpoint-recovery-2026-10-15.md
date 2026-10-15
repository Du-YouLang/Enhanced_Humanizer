# Pi PC-ALM验收检查点恢复

用户明确授权先恢复当前PC/P0/DeepSeek验收，再继续原85队列最后23个未开始格，详见[ADR-0046](../decisions/ADR-0046.md)。原61/85和历史27/112保留，额外单格补跑另列，累计USD250/10000不变。

原候选提交6d488ff7fe01c2f3155756e8285f49eac277e089；模型29次wire、258.815秒COMPLETED，公开测试PASS。原独立验收沙箱5f81bae6b3a7441a8c70902eb3b1cc0d有smoke1、anchor3、grid44份完整训练文件，另一grid不完整。源树/原输入指纹和run_artifacts校验后，完整48份作为只读恢复缓存。旧started和所有产物保持，缓存完整命令/配置必须匹配，未完成训练照原候选程序运行。报告与恢复计时另存，不把恢复时间当原完整执行时间。

新增恢复Journal只允许验收action，setup/model/public/freeze只读复用；候选clean Git/head/patch/source绑定不变。验收期间硬拒绝模型入口，要求累计账本字节不变。恢复完成追加记录并保留原不确定started，随后仅运行23个未开始格。原科学阈值、75格/两格独立校验、隔离/资源门禁和Sol科学审阅要求不变。

实际零provider绑定通过；真实科学隔离沙箱测试确认完整缓存训练跳过、缺失训练实际执行，配置参数不匹配立即拒绝，账本无变化。独立回归覆盖完成阶段不执行、验收恰好一次、再次中断拒绝自动重放和精确61/1/23分割。初次准备因smoke的CLI输出路径覆盖未计入配置校验而被拒绝；随后因恢复模块依赖路径未就绪被拒绝，两次均零模型、保留现场，修正恢复侧校验/导入后通过，候选未变。

实际模型启动、数值结果和科学接受取后续私有回执；准备不算已经恢复。Luna负责只读实核，Sol负责实现/科学，GitHub只按精确CI交付，产品每PR人审和外部发布确认保持。

## 实际恢复启动

20:13:42（北京时间）原批次063346以新owner363/boot8cdcaa48-aba9-4856-9bc5-0140a48a30f6/startticks175890/command72eaa4acd332e7c270b3203fd0204fd0fd8f978a5d50b4b354ff43e06a657d6e恢复。独立status和Luna实核存活；旧boot的364保留为已退出。控制器checkpoint-cc6783d37353efd7、恢复计划053bd12d555ef3c6017a04185335dc8348351b7874648b561dfe9a4a7f76c7bc。

精确功能77ee13052c492b6402059ed7cebffd08d3105ffb通过Windows267（9平台skip）、原生267（3平台skip）、Node8，真实隔离复用/未完成训练正控及命令不匹配拒绝，另三个真实源码/缓存/旧格重放负控全拒绝、账本不变。精确CI38732493048与38732485188的integrity/secrets/linux-budget全SUCCESS；[PR55](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/55)合并4623db893f741890a316b29564c44eeb0d06e115后启动，[Issue54](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/54)继续追踪实际结果。

验收时限扣除原中断前跨度的保守1900秒，只余5300秒。新隔离沙箱821a67022dad475abc42a989cc43e00b源与原候选相同，实际已出现48个缓存训练，随后训练旧未完成的N32/L128/PC-ALM。原沙箱与恢复证据逐文件hash再次通过；累计账本8683DS/242订阅/USD224.7939363保守上界、SHA21685592e51275e84662f727befd392950e26d360cf1077b60337d6f11c902bc保持，恢复验收模型调用0、现金实际unavailable。v17无需改动即可按新launch精确识别新owner；其历史主集baseline性质不变。

以上是实际恢复运行，尚非数值/科学完成。完成数仍61/85和累计88/112，额外单格1FAIL保持独立；验收闭合后只准衔接23未开始格。完整科学审阅和新版P7/外部发布仍待完成。
