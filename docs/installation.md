# 本地预览安装与交付

版本 `0.1.0-preview.1`，P7 范围为安装打包和交付准备。包以一个精确 Git commit 为来源；并非已发布产品，完整 P6 尚待验收。本机验证平台为 Windows + PowerShell + Python 3.12 及以上 + Git。没有重新实现或捆绑 Coding Harness。

源码包包含已提交源码、保留的需求基线、公开审计、固定依赖清单和一个离线 Git bundle。它不包含 `.local-workbench`、账号登录、模型原始记录、科研原文、数据库、Python/Conda 安装或 WSL VHD。完整运行状态需另行本地私有备份。原有单账号的 GitHub 连接继续暂缓，安装器不联网操作 Git。

## 校验并安装

从可信的本地源码目录运行安装器。`receipt.json` 提供 ZIP 的独立 SHA256；校验清单保证收到相同字节，不构成数字签名。不要用修改后的包内清单替代这份独立 SHA。所有新安装目录仍位于 `D:\Desktop\Enhanced_Humanizer\.local-workbench` 下。

```powershell
Set-Location D:\Desktop\Enhanced_Humanizer
.\scripts\install_workbench.ps1 `
  -Archive <交付ZIP的绝对路径> `
  -ExpectedSHA256 <receipt中的64位SHA256> `
  -Destination D:\Desktop\Enhanced_Humanizer\.local-workbench\installations\preview-1 `
  -PythonPath D:\Anaconda\python.exe
```

安装前验证每个成员路径、大小和 SHA，拒绝重复/Windows 大小写冲突/链接/额外成员；250 MiB 上限。随后在新目录恢复精确 Git 版本并逐文件与 ZIP 比对。已有目录拒绝覆盖，失败目录保留供诊断。Windows venv、pip 缓存和临时文件都放在该新安装的 `.local-workbench` 中；只安装 hash 固定的 PyYAML 6.0.3，下载失败则停止。界面本身只使用 Python 标准库。Python 和 Git 使用已存在的本机工具，安装器不替换它们，不改系统功能或执行重启。

## 启动与诊断

```powershell
$previewRoot = 'D:\Desktop\Enhanced_Humanizer\.local-workbench\installations\preview-1'
& "$previewRoot\scripts\start_workbench.ps1" -Port 8767
& "$previewRoot\.local-workbench\runtime\windows\Scripts\python.exe" -B "$previewRoot\scripts\doctor_workbench.py"
```

在本机浏览器直接打开 `http://127.0.0.1:8767`。端口被另一工作区或旧版服务占用时启动器报错，换端口即可；不会停止已有服务。启动器用 `/health` 的项目路径核对实例，并记录自己新建进程的 PID。HTTP owner/Origin/CSRF 和逐 PR 人工审核门禁继续有效，远程发布继续硬禁用。

安装预览的工程历史为空，真实推理启动默认关闭。现有开发目录的 P4/P5 验收文件、阶段账本及登录不会自动复制到预览，更不能当作新机器的授权。`doctor_workbench.py --native` 仅检查现有专用 WSL、非 root、pidfd、工具和认证文件是否存在；不会读取凭据内容、刷新登录或调用模型。检查成功不证明接口连通，也不代表 benchmark 已完成。

实际模型开发继续使用已验收的原工作区及 `EnhancedHumanizer-P0`。新机器启用完整运行须重新完成 P0 工具链/隔离/认证/预算验收，参照 `docs/local-setup.md`、ADR-0005/0006；本版本没有承诺跨主机即插即用。不得直接复制全局认证目录、取消 Windows 驱动隔离或由安装器自动创建/卸载 WSL。

## 本地构建与回滚

重要变更先提交，执行仓库完整性、治理测试和 Gitleaks（含 Git 历史），再构建干净源码：

```powershell
python -B scripts/package_workbench.py build --output .local-workbench\deliveries\<新的交付目录>
python -B scripts/package_workbench.py verify --archive <ZIP> --sha256 <独立SHA256>
```

输出目录已存在时拒绝覆盖。`source.bundle` 保留当前提交可达的 Git 历史；ZIP 中 Git blob 不受 Windows 换行转换影响，安装后逐文件检查。旧安装和私有状态保持原位，需要回滚时把已验证的旧包安装到另一个新目录，选择独立端口启动。不要对旧环境做递归删除或强制覆盖。

原工作区工程记忆可用 `python -B scripts/workbench.py export` 创建私有备份；恢复用 `restore --archive <本地备份ZIP> --destination <项目内新目录>`，再用 `verify --state <恢复目录>` 验证事件链。该备份含私有日志，不是源码交付包；Git bundle 不含未提交文件，须先提交或另存快照。不导入凭据，不备份 WSL OS；备份/恢复不会自动启动模型。

## 发布前门禁

发布前再次与用户确认名称、项目许可证、交付平台与公开内容；恢复 Du-YouLang 后按阶段实际跑远程 CI/PR，并核验身份。P6 公共主集、完整轨迹敏感性实验、科学材料和科研验收尚待完成或按用户明确范围继续暂缓。Jev 地区访问阻塞与未知成本明确保留。每一次产品 PR 均须新的人工审核；本地安装验证不授权发布。
