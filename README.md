# Autofill Login

Local browser automation script for filling account/password pairs into a login
or activation page. It is designed for local use: credentials are entered at
runtime and are not saved by the script.

## Features

- Opens the target page in a visible browser window.
- Supports one account or many `account:password` lines.
- Fills one account at a time.
- Waits for Enter before filling the next account.
- Can optionally click the submit/activate/login button after each fill.
- Uses a persistent browser profile so logged-in sessions can be reused.

## Requirements

- Windows PowerShell
- Python 3, available through the `py -3` launcher
- Playwright for Python

Install Playwright if needed:

```powershell
py -3 -m pip install playwright
py -3 -m playwright install chromium
```

## Usage

Run from this folder:

```powershell
cd H:\github
py -3 .\autofill_login.py
```

Paste credentials in this format, one per line:

```text
account1@example.com:password1
account2@example.com:password2
account3@example.com:password3
```

After pasting all lines, press Enter on an empty line.

The script fills the first account, then waits. When the page is ready for the
next account, return to PowerShell and press Enter.

## Auto Submit

To automatically click the submit/activate/login button after each fill:

```powershell
py -3 .\autofill_login.py --submit
```

## Options

```text
--url URL                 Target page URL.
--account ACCOUNT         Single account/email.
--password PASSWORD       Single password. Avoid this because shell history may save it.
--submit                  Click the submit/activate/login button after filling.
--profile-dir DIR         Browser profile directory.
--browser BROWSER         chromium, msedge, or chrome.
```

Example with a custom URL:

```powershell
py -3 .\autofill_login.py --url "https://example.com/login"
```

## Security Notes

- Do not commit or upload real credentials.
- Prefer pasting credentials only into the local PowerShell prompt.
- Avoid using `--password` on the command line because command history may
  record it.
- If credentials were exposed in chat, logs, screenshots, or commits, rotate or
  revoke them.

## Troubleshooting

If the script cannot find the fields, log in manually in the opened browser,
return to the target page, then press Enter in PowerShell to retry.

If Microsoft Edge is not available, run with Chromium:

```powershell
py -3 .\autofill_login.py --browser chromium
```
