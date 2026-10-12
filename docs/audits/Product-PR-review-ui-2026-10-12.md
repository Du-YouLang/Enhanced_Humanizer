# 产品 PR 人审界面修复

用户真实操作发现两项问题：选中审核提案后 Diff/测试为空；未填审核意见时点击批准，仅页底英文报错，成功响应也未立即刷新审核卡。

提案现在按关联实现 ID 与精确 head 显示真实 Git diff、冻结测试和原始日志，明确它们来自关联实现。缺实现或 head 已变拒绝关联及批准。审核卡新增必填意见框、就地错误/提交反馈、提交时禁用重复点击，成功后立即重绘状态。后台精确提交/证据/目标/一次性人审要求保持。

实际本机 8773 浏览器已核验预算提交 1ed608718e14e501452f0b9506cbae347ed7244c 的非空 diff、119 Windows 测试（7平台skip）、119 原生Linux全部通过的已保存结果，以及原生完整日志可展开。这些结果属于该精确提交，不是新界面代码的119项结果。新增5项 Node 回归覆盖提案关联、测试可见、提交变化拒绝、空意见不发批准请求和成功后发布按钮即时刷新；实际通过。代理未点击人工批准、未代写人类意见、未上传产品PR。

新界面提交不改变已准备的预算审核提案 head/证据/目标；页面中的实际人审/发布状态取事件库，不能由本修复记录推断已批准。截图与完整日志保存在私有审计目录，不上传浏览器会话或认证数据。

后续真实验收已通过：用户本人填写意见并批准，事件链依次记录 human_owner/HUMAN_APPROVED → controller/CONSUMED_BEFORE_EXTERNAL_ACTION → DRAFT_PR_CREATED_AWAITING_CI_AND_GITHUB_HUMAN_REVIEW，三者顺序和 hash 均独立核对。产品实际创建 [Draft PR #30](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/30)，head 精确为 `1ed608718e14e501452f0b9506cbae347ed7244c`，目标 main 在创建时为 `0abbaf03477fc1d35e00b9c14ec5e92480184d9c`；证据 hash 未变化。代理没有提交批准请求或代写意见。

这次 Draft PR 的新 CI run [38205876034](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38205876034) 中 integrity/secrets/linux-budget 全部实际 SUCCESS，未仅复用之前开发 PR 的同 head 检查。真实人审与一次性产品上传状态为 **PASS_REAL_HUMAN_APPROVAL_AND_PRODUCT_DRAFT_UPLOAD**，私有回执 `product-pr30-real-owner-receipt.private.json` 保存事件/精确 head/CI hash。Draft 仍待 GitHub 人类决定是否合并，对外产品发布未授权。未通过其他开发 PR 合并同一提交来绕过这个 Draft 的人工合并流程。
