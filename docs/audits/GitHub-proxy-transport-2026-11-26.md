# GitHub CLI 本机代理修复（2026-11-26）

问题是原生 gh 的默认连接路径被本机软件中断；不是已证实的令牌失效。相同现有凭据通过现有 HTTP 代理 `127.0.0.1:7897` 后，`gh api user` 实际返回 Du-YouLang，auth status 成功；仓库 push/admin 权限元数据、Actions 读取和 git ls-remote 都通过。没有增加权限、重登录、清除凭据或修改全局代理。GET 网页成功不能证明 gh 默认路由或设备授权 POST 成功。

项目入口仅在调用期间设置进程环境变量，并在 finally 恢复原值；不写系统/用户环境，不更改 WinHTTP、代理软件、WSL 网络、Git 全局设置或 TLS 验证。仅接受本地回环代理，默认端口7897。代理软件需处于运行状态。

```powershell
& 'D:\Desktop\Enhanced_Humanizer\scripts\invoke_project_github.ps1' -Arguments @('auth','status')
& 'D:\Desktop\Enhanced_Humanizer\scripts\invoke_project_github.ps1' -Arguments @('api','user','--jq','.login')
& 'D:\Desktop\Enhanced_Humanizer\scripts\invoke_project_github.ps1' -Tool git -Arguments @('ls-remote','origin','refs/heads/main')
```

本入口对被调用程序不额外授予仓库权限；产品逐 PR 人工审核关卡和发布确认不变。直接在其他 CMD/PowerShell 窗口运行 `gh` 不会自动继承本脚本的临时环境；如需在当前终端临时使用代理，可仅为该窗口设置 HTTP_PROXY/HTTPS_PROXY 后使用，关闭窗口即终止。

读检查不能证明实际 push、PR 创建或新 CI 已完成；新提交的交付以精确回执为准。原网络诊断及身份/权限检查回执保存在本机 `.local-workbench/audits/model-refresh-20261126/github-auth-network/`，不包含密钥。
