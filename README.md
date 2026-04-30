# Autofill Login

一个本地浏览器自动填写脚本，用来把账号和密码填写到登录页或激活页中。

脚本只在本机运行，账号密码在运行时输入，不会被脚本保存到文件。

## 功能

- 打开可见的浏览器窗口。
- 支持单个账号，也支持批量粘贴多行 `账号:密码`。
- 每次只填写一个账号。
- 填完当前账号后，等待你按 Enter 再继续下一个。
- 可选：填写后自动点击提交、登录或激活按钮。
- 可选：自动点击“开始激活”，等待操作日志出现密钥信息，保存密钥后自动继续下一个账号。
- 使用持久化浏览器配置，方便复用已经登录的会话。

## 环境要求

- Windows PowerShell
- Python 3，并且可以通过 `py -3` 启动
- Playwright for Python

如果没有安装 Playwright，先执行：

```powershell
py -3 -m pip install playwright
py -3 -m playwright install chromium
```

## 使用方法

进入项目目录：

```powershell
cd H:\github\autofill-login
```

启动脚本：

```powershell
py -3 .\autofill_login.py
```

然后按下面格式粘贴账号密码，一行一个：

```text
account1@example.com:password1
account2@example.com:password2
account3@example.com:password3
```

粘贴完成后，再按一次空行 Enter 结束录入。

脚本会先填写第一个账号。你在网页中处理完当前账号后，回到 PowerShell 按 Enter，脚本才会继续填写下一个。

## 运行模式

默认模式只负责填写账号密码，不会自动点击按钮：

```powershell
py -3 .\autofill_login.py
```

如果希望每次填写后自动点击提交、登录或激活按钮，使用：

```powershell
py -3 .\autofill_login.py --submit
```

这个模式点击按钮后，仍然会等待你按 Enter 再继续下一个账号。

如果希望脚本自动完成整轮流程，使用：

```powershell
py -3 .\autofill_login.py --auto-activate
```

自动激活模式会：

1. 填写账号密码。
2. 自动点击“开始激活”。
3. 等待操作日志出现“账号权益处理中”和“您的密钥”。
4. 提取新出现的 `sk-jb-...` 密钥。
5. 写入本地 `activation_keys.csv`。
6. 自动继续下一个账号。

`activation_keys.csv` 已经加入 `.gitignore`，不会默认提交到 GitHub。

## 常用参数

```text
--url URL                 要打开的目标页面地址。
--account ACCOUNT         单个账号或邮箱。
--password PASSWORD       单个密码。不推荐使用，命令历史可能会记录密码。
--submit                  填写后自动点击提交、登录或激活按钮。
--auto-activate           自动点击、等待激活日志、记录密钥并继续下一个账号。
--keys-file FILE          自动激活模式下保存密钥的 CSV 文件，默认 activation_keys.csv。
--activation-timeout SEC  每个账号等待激活日志和密钥的最长秒数，默认 2100。
--poll-interval SEC       自动激活模式下检查页面的间隔秒数，默认 2。
--profile-dir DIR         浏览器用户数据目录。
--browser BROWSER         浏览器类型：chromium、msedge 或 chrome。
```

指定其他页面地址：

```powershell
py -3 .\autofill_login.py --url "https://example.com/login"
```

使用 Chromium：

```powershell
py -3 .\autofill_login.py --browser chromium
```

## 安全提醒

- 不要把真实账号密码提交到 GitHub。
- 不要把 `activation_keys.csv` 或其他密钥文件提交到 GitHub。
- 建议只把账号密码粘贴到本地 PowerShell 提示符里。
- 不建议使用 `--password` 参数传密码，因为命令历史可能会保存它。
- 如果账号密码曾经出现在聊天记录、截图、日志或提交记录中，建议尽快修改密码或作废重建。

## 常见问题

如果脚本找不到输入框，可能是页面还没有登录或没有跳转到目标页面。

处理方法：

1. 在打开的浏览器里手动登录。
2. 回到目标页面。
3. 回到 PowerShell，按 Enter 让脚本重试。

如果 Microsoft Edge 不可用，可以改用 Chromium：

```powershell
py -3 .\autofill_login.py --browser chromium
```
