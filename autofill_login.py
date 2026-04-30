import argparse
import getpass
import re
import sys
from pathlib import Path


DEFAULT_URL = "https://juzixiaoguofan.replit.app/admin-panel/activate"


def import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("Missing dependency: playwright")
        print("Install it with:")
        print("  python -m pip install playwright")
        print("If Chromium is not available, also run:")
        print("  python -m playwright install chromium")
        sys.exit(1)

    return sync_playwright, PlaywrightTimeoutError


def first_visible(locator):
    count = locator.count()
    for index in range(count):
        item = locator.nth(index)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return locator.first if count else None


def fill_first(page, candidates, value, field_name, timeout_ms=2500):
    last_error = None

    for candidate in candidates:
        try:
            locator = candidate()
            element = first_visible(locator)
            if element is None:
                continue
            element.fill(value, timeout=timeout_ms)
            print(f"Filled {field_name}.")
            return True
        except Exception as exc:
            last_error = exc

    message = f"Could not find the {field_name} field."
    if last_error:
        message += f" Last error: {last_error}"
    raise RuntimeError(message)


def click_submit(page, timeout_ms=2500):
    button_names = re.compile(
        r"(开始激活|激活|提交|登录|登入|确定|下一步|activate|submit|login|sign in|continue)",
        re.I,
    )

    candidates = [
        lambda: page.get_by_role("button", name=button_names),
        lambda: page.locator("button").filter(has_text=button_names),
        lambda: page.locator("input[type='submit']"),
    ]

    for candidate in candidates:
        try:
            locator = candidate()
            element = first_visible(locator)
            if element is None:
                continue
            element.click(timeout=timeout_ms)
            print("Clicked submit button.")
            return True
        except Exception:
            continue

    raise RuntimeError("Could not find a submit button.")


def parse_credential_pair(text):
    if ":" not in text:
        return None

    account, password = text.split(":", 1)
    account = account.strip()
    password = password.strip()

    if not account:
        raise SystemExit("Account/email is empty in pasted pair.")
    if not password:
        raise SystemExit(f"Password is empty for {account}.")

    return account, password


def collect_credentials(args):
    if args.account or args.password:
        account = args.account or input("Account/email: ").strip()
        password = args.password or getpass.getpass("Password: ")

        if not account:
            raise SystemExit("Account/email is empty.")
        if not password:
            raise SystemExit("Password is empty.")

        return [(account, password)]

    credentials = []
    print("Enter one or more credentials.")
    print("Supported formats:")
    print("  account@example.com:password")
    print("  account@example.com  then type password when prompted")
    print("Paste multiple account:password lines, then press Enter on an empty line when finished.")

    while True:
        index = len(credentials) + 1
        line = input(f"Credential #{index}: ").strip()
        if not line:
            break

        pasted_pair = parse_credential_pair(line)
        if pasted_pair:
            credentials.append(pasted_pair)
            continue

        account = line
        password = getpass.getpass(f"Password #{index}: ")
        if not password:
            raise SystemExit(f"Password #{index} is empty.")

        credentials.append((account, password))

    if not credentials:
        raise SystemExit("No credentials entered.")

    return credentials


def wait_for_key(message):
    input(message)


def fill_form(page, account, password):
    email_candidates = [
        lambda: page.get_by_label(re.compile(r"(JetBrains.*邮箱|邮箱|email|mail|account)", re.I)),
        lambda: page.get_by_placeholder(re.compile(r"(邮箱|email|mail|account)", re.I)),
        lambda: page.locator("input[type='email']"),
        lambda: page.locator("input[name*='email' i], input[id*='email' i]"),
        lambda: page.locator("input[name*='mail' i], input[id*='mail' i]"),
        lambda: page.locator("input[type='text']").first,
    ]
    password_candidates = [
        lambda: page.get_by_label(re.compile(r"(JetBrains.*密码|密码|password)", re.I)),
        lambda: page.get_by_placeholder(re.compile(r"(密码|password)", re.I)),
        lambda: page.locator("input[type='password']"),
        lambda: page.locator("input[name*='password' i], input[id*='password' i]"),
        lambda: page.locator("input[name*='pwd' i], input[id*='pwd' i]"),
    ]

    fill_first(page, email_candidates, account, "account/email")
    fill_first(page, password_candidates, password, "password")


def main():
    parser = argparse.ArgumentParser(
        description="Open a login/activation page and fill account/password locally."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Page URL to open.")
    parser.add_argument(
        "--account",
        help="Single account/email. If omitted, prompt for multiple accounts locally.",
    )
    parser.add_argument("--password", help="Password. Prefer omitting this and typing it when prompted.")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Click the submit/activate/login button after filling.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(Path.home() / ".autofill_login_profile"),
        help="Persistent browser profile directory. Useful when the page needs you to stay logged in.",
    )
    parser.add_argument(
        "--browser",
        choices=("chromium", "msedge", "chrome"),
        default="msedge",
        help="Browser channel to use. msedge uses the installed Microsoft Edge if available.",
    )
    args = parser.parse_args()

    credentials = collect_credentials(args)

    sync_playwright, _ = import_playwright()

    with sync_playwright() as playwright:
        chromium = playwright.chromium
        launch_options = {"headless": False}
        if args.browser in ("msedge", "chrome"):
            launch_options["channel"] = args.browser

        context = chromium.launch_persistent_context(
            user_data_dir=args.profile_dir,
            **launch_options,
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")

        total = len(credentials)
        for index, (account, password) in enumerate(credentials, start=1):
            print(f"\nFilling account {index}/{total}: {account}")

            try:
                fill_form(page, account, password)
            except RuntimeError as exc:
                print(exc)
                print("If the page needs login first, finish it in the opened browser.")
                input("Then go back to the target page and press Enter here to retry...")
                fill_form(page, account, password)

            if args.submit:
                click_submit(page)
            else:
                print("Filled only. Check the page, then click the button manually if needed.")

            if index < total:
                wait_for_key(
                    "After this account is done and the page is ready, press Enter here to fill the next one..."
                )

        input("Press Enter here to close the browser...")
        context.close()


if __name__ == "__main__":
    main()
