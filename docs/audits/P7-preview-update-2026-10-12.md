# P7 本地安装预览更新

本次独立安装预览的精确提交为 `687778c2e55ab3cfb20f9344b332942f79c908a4`，开发PR #22已经在实际integrity/secrets/linux-budget三项CI成功后合并。本地main与origin/main在交付时同步到该提交；之后主集评测开发在阶段分支继续，不能把此安装测试套用到后续未打包的提交。

新包在项目私有 `.local-workbench/deliveries/p7-main-protocol-20261012-v1`，SHA256 `4c86f0a83af1db4b2c4ce52672fa5e2100274a17ec1dc2c69629719d2b4c3043`，1,432,781 bytes、266个payload/bundle成员。独立新目录安装的venv、哈希锁定依赖及doctor检查通过；未复制凭据，模型和远程发布保持关闭。

实际loopback HTTP验证通过：项目根/端口匹配，匿名/错误Host/跨站/错误Origin或CSRF拒绝，合法owner的模型启动和远程发布也拒绝，事件/运行保持为空。相同安装再次启动复用同一PID，不同安装占用端口明确拒绝，原服务保留。测试预览端口8771；不承诺该临时验证服务长期运行。

旧 `ef085e5abe5ca109a24bfd820138f20d252e5212` 包未覆盖，仍为SHA256 `6e3d2435c6854ac296eade00827d7984743cfe5f079f3d8bd5d47eea23f91fd5`。它已在另一新目录恢复，并复用已有Python验证旧源码/HTTP安全门禁；没有声称重新创建了旧venv或WSL。旧源码无remote、Git干净，原安装和失败历史全部保留。

完整本地Git refs备份已验证，bundle SHA256 `ad94d1cd1aac5347ee6f742f1c3577990ceb10342e2bc618098467ccd9fddceb`。本次P7操作模型请求0、外部发布0；源包、独立安装、HTTP、旧包回滚和端口控制回执保存在项目私有审计目录。

状态为 `PASS_LOCAL_PREVIEW_NOT_RELEASED`，并不代替完整P6结果。主集及最后源码/审计更新后还需生成最终精确交付包。产品每个PR仍要求真实人审；对外发布前仍须确认名称、许可、平台和内容。
