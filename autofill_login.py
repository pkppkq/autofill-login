import argparse
import csv
import getpass
import re
import sys
import time
from datetime import datetime
from pathlib import Path


DEFAULT_URL = "https://juzixiaoguofan.replit.app/admin-panel/activate"
SCRIPT_DIR = Path(__file__).resolve().parent
API_KEY_PATTERN = re.compile(r"sk-jb-[A-Za-z0-9_-]{24,}")


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


def page_text(page):
    return page.locator("body").inner_text(timeout=5000)


def extract_api_keys(text):
    return set(API_KEY_PATTERN.findall(text))


def find_activation_result(text, previous_keys):
    lines = text.splitlines()

    for line_index, line in enumerate(lines):
        if "您的密钥" not in line:
            continue

        new_keys = [key for key in API_KEY_PATTERN.findall(line) if key not in previous_keys]
        if not new_keys:
            continue

        nearby_start = max(0, line_index - 8)
        nearby_text = "\n".join(lines[nearby_start : line_index + 1])
        if "账号权益处理中" in nearby_text:
            return new_keys[-1], nearby_text

    return None, None


def wait_for_activation_result(page, previous_keys, timeout_seconds, poll_interval):
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            text = page_text(page)
            key, log_excerpt = find_activation_result(text, previous_keys)
            if key:
                return key, log_excerpt
        except Exception as exc:
            last_error = exc

        time.sleep(poll_interval)

    message = "Timed out waiting for activation log and new API key."
    if last_error:
        message += f" Last error: {last_error}"
    raise RuntimeError(message)


def resolve_output_path(file_path):
    output_path = Path(file_path)
    if not output_path.is_absolute():
        output_path = SCRIPT_DIR / output_path
    return output_path


def append_activation_key(keys_file, keys_text_file, account, api_key, page_url):
    saved_at = datetime.now().isoformat(timespec="seconds")

    output_path = resolve_output_path(keys_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not output_path.exists() or output_path.stat().st_size == 0

    with output_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if needs_header:
            writer.writerow(["time", "account", "api_key", "url"])
        writer.writerow([saved_at, account, api_key, page_url])

    text_path = None
    if keys_text_file:
        text_path = resolve_output_path(keys_text_file)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        with text_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{saved_at}] {account}\n")
            handle.write(f"{api_key}\n")
            handle.write(f"{page_url}\n\n")

    return output_path, text_path


def open_target_page(context, url, keep_extra_tabs):
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(url, wait_until="domcontentloaded")

    if keep_extra_tabs:
        return page

    for extra_page in list(context.pages):
        if extra_page == page:
            continue
        try:
            extra_page.close()
        except Exception:
            pass

    return page


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
        "--auto-activate",
        action="store_true",
        help="Click submit, wait for the activation log and new API key, save it, then continue automatically.",
    )
    parser.add_argument(
        "--keys-file",
        default="activation_keys.csv",
        help="CSV file used by --auto-activate to save API keys. Relative paths are saved next to this script.",
    )
    parser.add_argument(
        "--keys-text-file",
        default="activation_keys.txt",
        help="Text file used by --auto-activate to save API keys. Relative paths are saved next to this script.",
    )
    parser.add_argument(
        "--no-keys-text",
        action="store_true",
        help="Do not write the extra text file in --auto-activate mode.",
    )
    parser.add_argument(
        "--activation-timeout",
        type=int,
        default=2100,
        help="Seconds to wait for each activation result in --auto-activate mode.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between page checks in --auto-activate mode.",
    )
    parser.add_argument(
        "--no-start-wait",
        action="store_true",
        help="Start filling immediately after the page opens instead of waiting for Enter.",
    )
    parser.add_argument(
        "--keep-extra-tabs",
        action="store_true",
        help="Keep tabs restored by the persistent browser profile instead of closing them.",
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

        page = open_target_page(context, args.url, args.keep_extra_tabs)
        if not args.no_start_wait:
            wait_for_key(
                "Browser opened. Log in or navigate to the target page, then press Enter here to start filling..."
            )

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

            if args.auto_activate:
                previous_keys = extract_api_keys(page_text(page))
                click_submit(page)
                print("Waiting for activation log and new API key...")
                api_key, log_excerpt = wait_for_activation_result(
                    page,
                    previous_keys,
                    args.activation_timeout,
                    args.poll_interval,
                )
                csv_path, text_path = append_activation_key(
                    args.keys_file,
                    None if args.no_keys_text else args.keys_text_file,
                    account,
                    api_key,
                    page.url,
                )
                print(f"Recorded API key for {account}.")
                print(f"CSV: {csv_path}")
                if text_path:
                    print(f"Text: {text_path}")
                if log_excerpt:
                    print("Matched activation log:")
                    print(log_excerpt)
            elif args.submit:
                click_submit(page)
            else:
                print("Filled only. Check the page, then click the button manually if needed.")

            if index < total and not args.auto_activate:
                wait_for_key(
                    "After this account is done and the page is ready, press Enter here to fill the next one..."
                )

        input("Press Enter here to close the browser...")
        context.close()


if __name__ == "__main__":
    main()
