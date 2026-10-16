# STROKE legacy v4：显式motor对象的等价ROI表示

继承[v3](stroke-legacy-supplement-v3.md)全部数值、布尔、无NF与保留约束。只增加一种父进程表示白名单：`metadata.roi_order={"motor":[按序通道名]}`。对象必须仅有motor一个键，内值必须为字符串列表；与roi/roi_motor等其他出现的ROI表示及输入参考顺序逐一完全一致。其他对象、额外键、反序、冲突仍拒绝。只增加比较视图的canonical roi，不更改原JSON或数组。

原B程序同时写`roi_motor`列表及`roi_order.motor`同序列表，v3把两种容器直接比较，错误地当作冲突；这是表示适配器问题，不是14个数值失败。活动v3批次不改源码或裁判，原FAIL_NUMERIC及原因保留。仅在批次关闭后，对B的14份已保存产物另做v4只读复核并准备保存数组图，不执行候选或重跑数值。B的实际布尔输入拒绝失败继续保留，不能因为表示兼容就算整格PASS。
