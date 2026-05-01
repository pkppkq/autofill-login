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
- 可选：在“我的背包”页面批量把 `activation_keys.txt` 里的密钥加入成员列表。
- 可选：在“橘子机”页面批量捐献 `activation_keys.txt` 里的密钥，并记录进度。
- 可选：在“用量查询”页面批量查询 Key 容量和已使用次数，并写入结果文件。
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

浏览器打开目标页面后，脚本会先暂停。你可以先在浏览器里登录并回到激活页，然后回到 PowerShell 按 Enter，脚本才会开始填写账号。

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
5. 写入脚本同目录下的 `activation_keys.csv` 和 `activation_keys.txt`。
6. 自动继续下一个账号。

`activation_keys.csv` 和 `activation_keys.txt` 已经加入 `.gitignore`，不会默认提交到 GitHub。

等待日志和密钥时，PowerShell 会显示：

```text
While waiting: press Q to quit, or S to skip this account.
```

这时可以直接按：

- `Q`：退出整个脚本，并关闭自动化浏览器。
- `S`：跳过当前账号，重新打开目标页后继续处理下一个账号。

这两个按键不需要再按 Enter。

## 批量管理成员 Key

如果要在“我的背包”页面批量加入成员 Key，使用：

```powershell
py -3 .\autofill_login.py --add-member-keys
```

这个模式会：

1. 打开 `https://juzixiaoguofan.replit.app/admin-panel/backpack`。
2. 暂停等待，你先在浏览器里登录并确认已经回到背包页。
3. 你回到 PowerShell 按 Enter 后，脚本才开始操作页面。
4. 点击“管理成员”。
5. 从 `activation_keys.txt` 提取所有 `sk-jb-...`。
6. 逐个填入“输入要加入的 API Key”。
7. 点击“添加”。
8. 如果某个 Key 添加失败或等待超时，会打印失败原因并自动跳过，继续下一个 Key。

如果你只是想快速批量跑一遍，也可以使用旧别名：

```powershell
py -3 .\autofill_login.py --cycle-member-keys
```

`--cycle-member-keys` 现在只是 `--add-member-keys` 的别名，只会添加 Key，不会删除成员列表里的 Key。

出于安全考虑，脚本不会点击成员列表右侧的删除按钮。`--delete-after-add` 参数已经废弃，即使传入也会被忽略。

批量管理成员 Key 时，PowerShell 可以直接按：

- `Q`：退出脚本。
- `S`：跳过当前 Key。

这些按键在等待添加结果时也生效，不需要再按 Enter。

默认读取脚本同目录下的 `activation_keys.txt`。也可以指定其他文件：

```powershell
py -3 .\autofill_login.py --add-member-keys --member-keys-file "H:\path\keys.txt"
```

默认情况下，打开背包页后一定会等待你按 Enter 才开始添加。只有显式加 `--no-start-wait` 时，才会打开页面后直接开始操作。

## 批量捐献 Key

如果要在“橘子机”页面批量捐献保存的 Key，使用：

```powershell
py -3 .\autofill_login.py --donate-keys
```

这个模式会：

1. 打开 `https://juzixiaoguofan.replit.app/admin-panel/lottery`。
2. 暂停等待，你先在浏览器里登录并确认页面可用。
3. 你回到 PowerShell 按 Enter 后，脚本才开始操作页面。
4. 点击“我要当圣人”。
5. 从 `activation_keys.txt` 提取所有 `sk-jb-...`。
6. 逐个填入“要捐献的 JB KEY”。
7. 点击“捐献 Key”。
8. 如果显示“捐献成功”，记录成功并继续下一个。
9. 如果显示“Key 不存在或已被删除，无法捐献”，记录失败并自动跳过下一个。
10. 如果等待超时或页面报错，也记录原因并自动跳过下一个。

捐献时，PowerShell 可以直接按：

- `Q`：退出脚本，并保存当前进度。
- `S`：跳过当前 Key，保存进度后继续下一个。

这些按键在等待捐献结果时也生效，不需要再按 Enter。

默认会从上次停止的位置继续。进度保存在：

```text
H:\github\autofill-login\donation_progress.json
```

每个 Key 的结果会追加记录到：

```text
H:\github\autofill-login\donation_results.csv
```

如果所有当前 Key 都捐献完，进度会记录为当前文件长度。以后 `activation_keys.txt` 新增 Key 后，再运行 `--donate-keys` 会从新增的 Key 开始。

如果要从第一个 Key 重新开始：

```powershell
py -3 .\autofill_login.py --donate-keys --donation-restart
```

如果要从指定序号开始，例如从第 20 个 Key 开始：

```powershell
py -3 .\autofill_login.py --donate-keys --donation-start-index 20
```

默认情况下，打开橘子机页面后一定会等待你按 Enter 才开始捐献。只有显式加 `--no-start-wait` 时，才会打开页面后直接开始操作。

## 批量查询用量

如果要批量查询保存 Key 的容量和已使用次数，使用：

```powershell
py -3 .\autofill_login.py --query-usage
```

这个模式会：

1. 打开 `https://juzixiaoguofan.replit.app/admin-panel/my-key`。
2. 暂停等待，你先在浏览器里登录并确认页面可用。
3. 你回到 PowerShell 按 Enter 后，脚本才开始操作页面。
4. 从 `activation_keys.txt` 提取所有 `sk-jb-...`。
5. 逐个填入“输入您的 API 密钥”。
6. 点击“查询”。
7. 如果显示 `已使用 0 / 25 次` 这类结果，会记录已用次数、总容量、剩余次数和消耗百分比。
8. 如果显示“密钥不存在或无效”，也会写入结果文件并继续下一个。
9. 如果等待超时或页面报错，会记录错误原因并自动跳过下一个。

查询时，PowerShell 可以直接按：

- `Q`：退出脚本。
- `S`：跳过当前 Key。

这些按键在等待查询结果时也生效，不需要再按 Enter。

查询结果会写入：

```text
H:\github\autofill-login\usage_results.txt
H:\github\autofill-login\usage_results.csv
```

`usage_results.txt` 适合直接打开查看；`usage_results.csv` 适合用 Excel、WPS 或脚本继续处理。

这两个用量结果文件会包含完整 Key，已经加入 `.gitignore`，不要手动提交到 GitHub。

默认读取脚本同目录下的 `activation_keys.txt`。也可以指定其他文件：

```powershell
py -3 .\autofill_login.py --query-usage --usage-keys-file "H:\path\keys.txt"
```

默认情况下，打开用量查询页面后一定会等待你按 Enter 才开始查询。只有显式加 `--no-start-wait` 时，才会打开页面后直接开始操作。

## 密钥保存位置

自动激活模式拿到密钥后，会自动新建并追加写入下面两个本地文件：

```text
H:\github\autofill-login\activation_keys.csv
H:\github\autofill-login\activation_keys.txt
```

`activation_keys.txt` 适合直接打开查看，内容格式类似：

```text
[2026-05-01T23:10:00] account@example.com
sk-jb-xxxxxxxxxxxxxxxxxxxxxxxx
https://juzixiaoguofan.replit.app/admin-panel/activate
```

`activation_keys.csv` 适合用 Excel、WPS 或脚本继续处理，字段包含：

```text
time,account,api_key,url
```

如果从其他目录启动脚本，密钥文件仍然会保存到脚本所在目录，不会散落到当前 PowerShell 目录。

## 常用参数

```text
--url URL                 要打开的目标页面地址。
--account ACCOUNT         单个账号或邮箱。
--password PASSWORD       单个密码。不推荐使用，命令历史可能会记录密码。
--submit                  填写后自动点击提交、登录或激活按钮。
--auto-activate           自动点击、等待激活日志、记录密钥并继续下一个账号。
--add-member-keys         打开背包页，批量把密钥添加为成员 Key。
--donate-keys             打开橘子机页，批量捐献保存的 Key。
--query-usage             打开用量查询页，批量查询 Key 容量和已使用次数。
--usage-url URL           批量用量查询模式使用的页面地址。
--usage-keys-file FILE    批量用量查询模式读取的密钥文件，默认 activation_keys.txt。
--usage-results-file FILE 用量查询 TXT 结果文件，默认 usage_results.txt。
--usage-csv-file FILE     用量查询 CSV 结果文件，默认 usage_results.csv。
--usage-timeout SEC       每个 Key 等待查询结果的秒数，默认 15。
--usage-delay SEC         点击查询后开始读取结果前的暂停秒数，默认 0.8。
--donation-url URL        批量捐献模式使用的橘子机页面地址。
--donation-keys-file FILE 批量捐献模式读取的密钥文件，默认 activation_keys.txt。
--donation-state-file FILE 捐献进度 JSON 文件，默认 donation_progress.json。
--donation-results-file FILE 捐献结果 CSV 文件，默认 donation_results.csv。
--donation-restart        从第一个 Key 重新开始捐献。
--donation-start-index N  从指定的 1-based Key 序号开始捐献。
--donation-timeout SEC    每个 Key 等待捐献结果的秒数，默认 20。
--donation-delay SEC      每次捐献尝试后的暂停秒数，默认 0.8。
--cycle-member-keys       旧别名，等同于 --add-member-keys，不会删除成员 Key。
--backpack-url URL        批量成员 Key 模式使用的背包页地址。
--member-keys-file FILE   批量成员 Key 模式读取的密钥文件，默认 activation_keys.txt。
--delete-after-add        已废弃并被忽略，不会删除成员 Key。
--member-key-timeout SEC  每个成员 Key 添加结果的等待秒数，默认 15。
--member-key-delay SEC    每个成员 Key 操作后的暂停秒数，默认 0.8。
--keys-file FILE          自动激活模式下保存密钥的 CSV 文件，默认 activation_keys.csv。
--keys-text-file FILE     自动激活模式下保存密钥的 TXT 文档，默认 activation_keys.txt。
--no-keys-text            不生成额外的 TXT 文档，只保存 CSV。
--activation-timeout SEC  每个账号等待激活日志和密钥的最长秒数，默认 2100。
--poll-interval SEC       自动激活模式下检查页面的间隔秒数，默认 2。
--no-start-wait           打开页面后不等待 Enter，直接开始填写。
--keep-extra-tabs         保留浏览器配置自动恢复出来的其他标签页。
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
- 不要把 `activation_keys.csv`、`activation_keys.txt`、`donation_progress.json`、`donation_results.csv`、`usage_results.txt`、`usage_results.csv` 或其他密钥文件提交到 GitHub。
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
