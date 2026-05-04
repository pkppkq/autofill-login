import argparse
import csv
import getpass
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path


DEFAULT_URL = "https://juzixiaoguofan.replit.app/admin-panel/activate"
DEFAULT_BACKPACK_URL = "https://juzixiaoguofan.replit.app/admin-panel/backpack"
DEFAULT_DONATION_URL = "https://juzixiaoguofan.replit.app/admin-panel/lottery"
DEFAULT_USAGE_URL = "https://juzixiaoguofan.replit.app/admin-panel/my-key"
DEFAULT_CHECKIN_URL = "https://juzixiaoguofan.xyz/admin-panel/personal-center"
SCRIPT_DIR = Path(__file__).resolve().parent
API_KEY_PATTERN = re.compile(r"sk-jb-[A-Za-z0-9_-]{24,}")


class ActivationWaitCancelled(Exception):
    pass


class ActivationWaitSkipped(Exception):
    pass


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


def read_wait_command():
    if not (sys.platform.startswith("win") and sys.stdin.isatty()):
        return None

    import msvcrt

    while msvcrt.kbhit():
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            if msvcrt.kbhit():
                msvcrt.getwch()
            continue

        key = key.lower()
        if key == "q":
            return "quit"
        if key == "s":
            return "skip"

    return None


def wait_for_activation_result(page, previous_keys, timeout_seconds, poll_interval):
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        command = read_wait_command()
        if command == "quit":
            raise ActivationWaitCancelled("User requested exit while waiting for activation.")
        if command == "skip":
            raise ActivationWaitSkipped("User requested skipping the current account.")

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


def load_api_keys(keys_file):
    path = resolve_output_path(keys_file)
    if not path.exists():
        raise SystemExit(f"API key file does not exist: {path}")

    text = path.read_text(encoding="utf-8")
    keys = []
    seen = set()
    for key in API_KEY_PATTERN.findall(text):
        if key in seen:
            continue
        keys.append(key)
        seen.add(key)

    if not keys:
        raise SystemExit(f"No API keys found in: {path}")

    return keys, path


def mask_api_key(api_key):
    prefix = "sk-jb-"
    if not api_key.startswith(prefix) or len(api_key) < len(prefix) + 8:
        return api_key
    body = api_key[len(prefix) :]
    return f"{prefix}{body[:4]}****{body[-4:]}"


def key_fingerprint(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def read_json_file(file_path):
    path = resolve_output_path(file_path)
    if not path.exists():
        return {}, path

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle), path


def write_json_file(file_path, data):
    path = resolve_output_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def append_csv_row(file_path, header, row):
    path = resolve_output_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if needs_header:
            writer.writerow(header)
        writer.writerow(row)
    return path


def find_member_key_input(page, timeout_ms=2500):
    candidates = [
        lambda: page.get_by_placeholder(re.compile(r"(输入要加入的 API Key|API Key|key)", re.I)),
        lambda: page.locator("input[placeholder*='API' i]"),
        lambda: page.locator("input[placeholder*='key' i]"),
        lambda: page.locator("input").last,
    ]

    last_error = None
    for candidate in candidates:
        try:
            locator = candidate()
            element = first_visible(locator)
            if element is None:
                continue
            element.wait_for(state="visible", timeout=timeout_ms)
            return element
        except Exception as exc:
            last_error = exc

    message = "Could not find the member API key input."
    if last_error:
        message += f" Last error: {last_error}"
    raise RuntimeError(message)


def click_text_or_clickable_ancestor(page, texts):
    return page.evaluate(
        """
        (texts) => {
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== "hidden" &&
                    style.display !== "none" &&
                    rect.width > 0 &&
                    rect.height > 0;
            };
            const textOf = (el) => (el.innerText || el.textContent || "").trim();
            const matches = (el) => texts.some((text) => textOf(el).includes(text));
            const nodes = Array.from(document.querySelectorAll("button, [role='button'], a, div, span, p"))
                .filter((el) => visible(el) && matches(el))
                .sort((a, b) => textOf(a).length - textOf(b).length);

            for (const node of nodes) {
                let current = node;
                while (current && current !== document.body) {
                    if (visible(current)) {
                        const style = window.getComputedStyle(current);
                        const role = current.getAttribute("role");
                        const tag = current.tagName.toLowerCase();
                        if (
                            tag === "button" ||
                            tag === "a" ||
                            role === "button" ||
                            style.cursor === "pointer" ||
                            typeof current.onclick === "function"
                        ) {
                            current.scrollIntoView({ block: "center", inline: "center" });
                            current.click();
                            return true;
                        }
                    }
                    current = current.parentElement;
                }

                node.scrollIntoView({ block: "center", inline: "center" });
                node.click();
                return true;
            }

            return false;
        }
        """,
        texts,
    )


def member_manager_debug_state(page):
    try:
        text = page_text(page)
    except Exception as exc:
        return f"Could not read page text: {exc}"

    checks = [
        ("管理成员", "管理成员" in text),
        ("收起成员", "收起成员" in text),
        ("输入要加入", "输入要加入" in text),
        ("API Key", "API Key" in text),
    ]
    return ", ".join(f"{label}={'yes' if found else 'no'}" for label, found in checks)


def open_member_manager(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass

    try:
        return find_member_key_input(page, timeout_ms=1000)
    except RuntimeError:
        pass

    for text in ("我的宝可梦球", "我的背包", "key1"):
        try:
            target = page.get_by_text(text).first
            target.scroll_into_view_if_needed(timeout=1500)
            break
        except Exception:
            continue

    manage_member_text = re.compile(r"(管理成员|展开成员|成员管理)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=manage_member_text),
        lambda: page.locator("button").filter(has_text=manage_member_text),
        lambda: page.locator("[role='button']").filter(has_text=manage_member_text),
        lambda: page.get_by_text(manage_member_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.scroll_into_view_if_needed(timeout=1500)
            element.click(timeout=2500)
            return find_member_key_input(page, timeout_ms=5000)
        except Exception:
            continue

    try:
        if click_text_or_clickable_ancestor(page, ["管理成员", "展开成员", "成员管理"]):
            return find_member_key_input(page, timeout_ms=5000)
    except Exception:
        pass

    raise RuntimeError(f"Could not open member manager. Page state: {member_manager_debug_state(page)}")


def click_add_member_key(page, timeout_ms=2500):
    add_button_text = re.compile(r"(\+\s*添加|添加|add)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=add_button_text),
        lambda: page.locator("button").filter(has_text=add_button_text),
        lambda: page.get_by_text(add_button_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.click(timeout=timeout_ms)
            return True
        except Exception:
            continue

    raise RuntimeError("Could not find the add member button.")


def wait_for_member_key(page, api_key, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    marker = mask_api_key(api_key)

    while time.monotonic() < deadline:
        command = read_wait_command()
        if command == "quit":
            raise ActivationWaitCancelled("User requested exit while waiting for member key.")
        if command == "skip":
            raise ActivationWaitSkipped("User requested skipping the current member key.")

        text = page_text(page)
        if api_key in text or marker in text:
            return marker
        time.sleep(0.5)

    raise RuntimeError(f"Timed out waiting for member key to appear: {marker}")


def add_member_keys(page, api_keys, args):
    input_box = open_member_manager(page)
    total = len(api_keys)

    print(f"Loaded {total} API key(s).")
    print("During this mode: press Q to quit, or S to skip the current key.")
    if args.delete_after_add:
        print("Warning: --delete-after-add is disabled for safety. Member keys will not be deleted.")

    for index, api_key in enumerate(api_keys, start=1):
        command = read_wait_command()
        if command == "quit":
            print("User requested exit before adding the next member key.")
            break
        if command == "skip":
            print("Skipped one pending key.")
            continue

        marker = mask_api_key(api_key)
        print(f"\nAdding member key {index}/{total}: {marker}")

        try:
            input_box.fill(api_key)
            click_add_member_key(page)
            appeared_marker = wait_for_member_key(page, api_key, args.member_key_timeout)
            print(f"Added: {appeared_marker}")
            input_box.fill("")
        except ActivationWaitSkipped as exc:
            print(f"{exc} Moving to the next key.")
        except ActivationWaitCancelled as exc:
            print(exc)
            break
        except Exception as exc:
            print(f"Failed: {marker}. Reason: {exc}")
            print("Skipping this key and moving to the next one.")
            try:
                input_box = find_member_key_input(page, timeout_ms=1000)
                input_box.fill("")
            except Exception:
                pass

        time.sleep(args.member_key_delay)
        try:
            input_box = find_member_key_input(page, timeout_ms=5000)
        except Exception as exc:
            print(f"Could not refresh member key input after {marker}. Reason: {exc}")
            print("Trying to reopen member manager before the next key.")
            try:
                input_box = open_member_manager(page)
            except Exception as reopen_exc:
                print(f"Could not reopen member manager. Reason: {reopen_exc}")
                print("Stopping member key mode.")
                break


def find_donation_input(page, timeout_ms=2500):
    candidates = [
        lambda: page.get_by_placeholder(re.compile(r"(粘贴 Key|捐献|JB KEY|key)", re.I)),
        lambda: page.locator("input[placeholder*='Key' i]"),
        lambda: page.locator("input[placeholder*='key' i]"),
        lambda: page.locator("input").last,
    ]

    last_error = None
    for candidate in candidates:
        try:
            locator = candidate()
            element = first_visible(locator)
            if element is None:
                continue
            element.wait_for(state="visible", timeout=timeout_ms)
            return element
        except Exception as exc:
            last_error = exc

    message = "Could not find the donation key input."
    if last_error:
        message += f" Last error: {last_error}"
    raise RuntimeError(message)


def open_donation_dialog(page):
    try:
        return find_donation_input(page, timeout_ms=1000)
    except RuntimeError:
        pass

    donate_entry_text = re.compile(r"(我要当圣人|圣人计划|捐献 Key|捐献Key)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=donate_entry_text),
        lambda: page.locator("button").filter(has_text=donate_entry_text),
        lambda: page.locator("[role='button']").filter(has_text=donate_entry_text),
        lambda: page.get_by_text(donate_entry_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.scroll_into_view_if_needed(timeout=1500)
            element.click(timeout=2500)
            return find_donation_input(page, timeout_ms=5000)
        except Exception:
            continue

    try:
        if click_text_or_clickable_ancestor(page, ["我要当圣人", "圣人计划"]):
            return find_donation_input(page, timeout_ms=5000)
    except Exception:
        pass

    raise RuntimeError("Could not open donation dialog.")


def click_donate_key_button(page, timeout_ms=2500):
    button_text = re.compile(r"(捐献\s*Key|捐献Key|捐献)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=button_text),
        lambda: page.locator("button").filter(has_text=button_text),
        lambda: page.get_by_text(button_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.click(timeout=timeout_ms)
            return True
        except Exception:
            continue

    raise RuntimeError("Could not find the donate key button.")


def wait_for_donation_result(page, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        command = read_wait_command()
        if command == "quit":
            raise ActivationWaitCancelled("User requested exit while waiting for donation result.")
        if command == "skip":
            raise ActivationWaitSkipped("User requested skipping the current donation key.")

        text = page_text(page)
        if "捐献成功" in text:
            return "success", "捐献成功"
        if "Key 不存在" in text or "已被删除" in text or "无法捐献" in text:
            return "invalid", "Key 不存在或已被删除，无法捐献"
        if "失败" in text or "错误" in text:
            return "failed", "页面显示失败或错误"

        time.sleep(0.5)

    raise RuntimeError("Timed out waiting for donation result.")


def close_donation_success(page):
    close_text = re.compile(r"(好的，去抽奖|去抽奖|好的|确定)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=close_text),
        lambda: page.locator("button").filter(has_text=close_text),
        lambda: page.get_by_text(close_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.click(timeout=2500)
            return True
        except Exception:
            continue

    return False


def close_donation_dialog(page):
    close_text = re.compile(r"(取消|关闭|close|cancel)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=close_text),
        lambda: page.locator("button").filter(has_text=close_text),
        lambda: page.get_by_text(close_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.click(timeout=1500)
            return True
        except Exception:
            continue

    return False


def resolve_donation_start_index(args, key_count):
    if args.donation_start_index is not None:
        start_index = max(0, args.donation_start_index - 1)
        return min(start_index, key_count), None, None

    state, state_path = read_json_file(args.donation_state_file)
    if args.donation_restart:
        return 0, state, state_path

    next_index = state.get("next_index", 0)
    if not isinstance(next_index, int):
        next_index = 0

    return min(max(next_index, 0), key_count), state, state_path


def save_donation_progress(args, keys_path, next_index, total_keys, status, result=None):
    state = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "keys_file": str(keys_path),
        "next_index": next_index,
        "next_key_number": next_index + 1 if next_index < total_keys else None,
        "total_keys_seen": total_keys,
        "completed_all_seen_keys": next_index >= total_keys,
        "status": status,
    }
    if result:
        state["last_result"] = result
    return write_json_file(args.donation_state_file, state)


def append_donation_result(args, index, total_keys, api_key, status, detail):
    return append_csv_row(
        args.donation_results_file,
        ["time", "key_number", "total_keys", "key_masked", "key_hash", "status", "detail"],
        [
            datetime.now().isoformat(timespec="seconds"),
            index + 1,
            total_keys,
            mask_api_key(api_key),
            key_fingerprint(api_key),
            status,
            detail,
        ],
    )


def donate_keys(page, api_keys, keys_path, args):
    total = len(api_keys)
    start_index, _, state_path = resolve_donation_start_index(args, total)
    if state_path is None:
        state_path = resolve_output_path(args.donation_state_file)

    if start_index >= total:
        save_donation_progress(args, keys_path, total, total, "complete")
        print(f"No pending donation keys. Progress already covers {total}/{total} key(s).")
        print(f"Progress: {state_path}")
        return

    print(f"Loaded {total} donation key(s) from: {keys_path}")
    print(f"Starting from key {start_index + 1}/{total}.")
    print("During donation: press Q to quit, or S to skip the current key.")

    for index in range(start_index, total):
        api_key = api_keys[index]
        marker = mask_api_key(api_key)

        command = read_wait_command()
        if command == "quit":
            save_donation_progress(args, keys_path, index, total, "stopped")
            print("User requested exit before donating the next key.")
            break
        if command == "skip":
            append_donation_result(args, index, total, api_key, "skipped", "user skipped before donation")
            save_donation_progress(args, keys_path, index + 1, total, "running")
            print(f"Skipped: {marker}")
            continue

        print(f"\nDonating key {index + 1}/{total}: {marker}")

        try:
            input_box = open_donation_dialog(page)
            input_box.fill(api_key)
            click_donate_key_button(page)
            status, detail = wait_for_donation_result(page, args.donation_timeout)

            if status == "success":
                print(f"Donated: {marker}")
                close_donation_success(page)
            else:
                print(f"Donation failed: {marker}. Reason: {detail}")
                close_donation_dialog(page)

            append_donation_result(args, index, total, api_key, status, detail)
            save_donation_progress(
                args,
                keys_path,
                index + 1,
                total,
                "running",
                {
                    "key_number": index + 1,
                    "key_masked": marker,
                    "key_hash": key_fingerprint(api_key),
                    "result": status,
                    "detail": detail,
                },
            )
        except ActivationWaitSkipped as exc:
            print(f"{exc} Moving to the next key.")
            append_donation_result(args, index, total, api_key, "skipped", str(exc))
            save_donation_progress(args, keys_path, index + 1, total, "running")
        except ActivationWaitCancelled as exc:
            print(exc)
            save_donation_progress(args, keys_path, index, total, "stopped")
            break
        except Exception as exc:
            print(f"Donation error: {marker}. Reason: {exc}")
            print("Skipping this key and moving to the next one.")
            append_donation_result(args, index, total, api_key, "error", str(exc))
            save_donation_progress(
                args,
                keys_path,
                index + 1,
                total,
                "running",
                {
                    "key_number": index + 1,
                    "key_masked": marker,
                    "key_hash": key_fingerprint(api_key),
                    "result": "error",
                    "detail": str(exc),
                },
            )

        time.sleep(args.donation_delay)
    else:
        progress_path = save_donation_progress(args, keys_path, total, total, "complete")
        print(f"Finished donating all currently loaded keys: {total}/{total}.")
        print(f"Progress: {progress_path}")


def find_usage_input(page, timeout_ms=2500):
    candidates = [
        lambda: page.get_by_placeholder(re.compile(r"(输入您的 API 密钥|API 密钥|API key|key)", re.I)),
        lambda: page.locator("input[placeholder*='API' i]"),
        lambda: page.locator("input[placeholder*='key' i]"),
        lambda: page.locator("input").last,
    ]

    last_error = None
    for candidate in candidates:
        try:
            locator = candidate()
            element = first_visible(locator)
            if element is None:
                continue
            element.wait_for(state="visible", timeout=timeout_ms)
            return element
        except Exception as exc:
            last_error = exc

    message = "Could not find the usage query input."
    if last_error:
        message += f" Last error: {last_error}"
    raise RuntimeError(message)


def click_usage_query_button(page, timeout_ms=2500):
    query_text = re.compile(r"(查询|search|query)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=query_text),
        lambda: page.locator("button").filter(has_text=query_text),
        lambda: page.get_by_text(query_text),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.click(timeout=timeout_ms)
            return True
        except Exception:
            continue

    raise RuntimeError("Could not find the usage query button.")


def parse_usage_result(text):
    if "密钥不存在或无效" in text:
        return {
            "status": "invalid",
            "used": "",
            "capacity": "",
            "remaining": "",
            "percent": "",
            "detail": "密钥不存在或无效",
        }

    usage_match = re.search(r"(\d+)\s*/\s*(\d+)(?:\s*次)?", text)
    if not usage_match:
        return None

    used = int(usage_match.group(1))
    capacity = int(usage_match.group(2))
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%(?:\s*已消耗)?", text)
    percent = percent_match.group(1) if percent_match else ""

    return {
        "status": "valid",
        "used": used,
        "capacity": capacity,
        "remaining": max(capacity - used, 0),
        "percent": percent,
        "detail": f"已使用 {used} / {capacity} 次",
    }


def wait_for_usage_result(page, timeout_seconds, previous_text=None):
    deadline = time.monotonic() + timeout_seconds
    started_at = time.monotonic()

    while time.monotonic() < deadline:
        command = read_wait_command()
        if command == "quit":
            raise ActivationWaitCancelled("User requested exit while waiting for usage result.")
        if command == "skip":
            raise ActivationWaitSkipped("User requested skipping the current usage key.")

        text = page_text(page)
        result = parse_usage_result(text)
        if result:
            if previous_text is not None and text == previous_text and time.monotonic() - started_at < 3:
                time.sleep(0.5)
                continue
            return result

        time.sleep(0.5)

    raise RuntimeError("Timed out waiting for usage query result.")


def append_usage_result(args, index, total_keys, api_key, result):
    saved_at = datetime.now().isoformat(timespec="seconds")
    key_masked = mask_api_key(api_key)
    key_hash = key_fingerprint(api_key)
    text_path = resolve_output_path(args.usage_results_file)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    with text_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{saved_at}] key {index + 1}/{total_keys}\n")
        handle.write(f"key: {api_key}\n")
        handle.write(f"key_masked: {key_masked}\n")
        handle.write(f"key_hash: {key_hash}\n")
        handle.write(f"status: {result['status']}\n")
        handle.write(f"used: {result['used']}\n")
        handle.write(f"capacity: {result['capacity']}\n")
        handle.write(f"remaining: {result['remaining']}\n")
        handle.write(f"percent_consumed: {result['percent']}\n")
        handle.write(f"detail: {result['detail']}\n\n")

    csv_path = append_csv_row(
        args.usage_csv_file,
        [
            "time",
            "key_number",
            "total_keys",
            "key",
            "key_masked",
            "key_hash",
            "status",
            "used",
            "capacity",
            "remaining",
            "percent_consumed",
            "detail",
        ],
        [
            saved_at,
            index + 1,
            total_keys,
            api_key,
            key_masked,
            key_hash,
            result["status"],
            result["used"],
            result["capacity"],
            result["remaining"],
            result["percent"],
            result["detail"],
        ],
    )

    return text_path, csv_path


def query_key_usage(page, api_keys, keys_path, args):
    total = len(api_keys)
    input_box = find_usage_input(page, timeout_ms=5000)

    print(f"Loaded {total} usage query key(s) from: {keys_path}")
    print("During usage query: press Q to quit, or S to skip the current key.")

    for index, api_key in enumerate(api_keys):
        command = read_wait_command()
        if command == "quit":
            print("User requested exit before querying the next key.")
            break
        if command == "skip":
            print("Skipped one pending key.")
            continue

        marker = mask_api_key(api_key)
        print(f"\nQuerying key {index + 1}/{total}: {marker}")

        try:
            previous_text = page_text(page)
            input_box.fill(api_key)
            click_usage_query_button(page)
            time.sleep(args.usage_delay)
            result = wait_for_usage_result(page, args.usage_timeout, previous_text)
            text_path, csv_path = append_usage_result(args, index, total, api_key, result)
            if result["status"] == "valid":
                print(
                    f"Usage: {marker} used {result['used']} / {result['capacity']}, remaining {result['remaining']}."
                )
            else:
                print(f"Usage query result: {marker} {result['detail']}.")
            print(f"Text: {text_path}")
            print(f"CSV: {csv_path}")
            input_box = find_usage_input(page, timeout_ms=2000)
            input_box.fill("")
        except ActivationWaitSkipped as exc:
            print(f"{exc} Moving to the next key.")
        except ActivationWaitCancelled as exc:
            print(exc)
            break
        except Exception as exc:
            result = {
                "status": "error",
                "used": "",
                "capacity": "",
                "remaining": "",
                "percent": "",
                "detail": str(exc),
            }
            text_path, csv_path = append_usage_result(args, index, total, api_key, result)
            print(f"Usage query failed: {marker}. Reason: {exc}")
            print("Skipping this key and moving to the next one.")
            print(f"Text: {text_path}")
            print(f"CSV: {csv_path}")
            try:
                input_box = find_usage_input(page, timeout_ms=1000)
                input_box.fill("")
            except Exception:
                pass

    print("Usage query mode finished.")


def parse_checkin_numbers(text):
    def labeled_number(label):
        match = re.search(rf"{label}\s*\n?\s*(\d+)", text)
        return int(match.group(1)) if match else ""

    daily_match = re.search(r"今日全站剩余\s*(\d+)\s*/\s*(\d+)", text)
    daily_remaining = int(daily_match.group(1)) if daily_match else ""
    daily_limit = int(daily_match.group(2)) if daily_match else ""

    return {
        "total_quota": labeled_number("总额度"),
        "used_quota": labeled_number("已使用"),
        "daily_remaining": daily_remaining,
        "daily_limit": daily_limit,
    }


def append_checkin_result(args, result, page_url):
    saved_at = datetime.now().isoformat(timespec="seconds")
    numbers = result.get("numbers", {})
    text_path = resolve_output_path(args.checkin_log_file)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    with text_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{saved_at}]\n")
        handle.write(f"status: {result['status']}\n")
        handle.write(f"detail: {result['detail']}\n")
        handle.write(f"total_quota: {numbers.get('total_quota', '')}\n")
        handle.write(f"used_quota: {numbers.get('used_quota', '')}\n")
        handle.write(f"daily_remaining: {numbers.get('daily_remaining', '')}\n")
        handle.write(f"daily_limit: {numbers.get('daily_limit', '')}\n")
        handle.write(f"url: {page_url}\n\n")

    csv_path = append_csv_row(
        args.checkin_csv_file,
        [
            "time",
            "status",
            "detail",
            "total_quota",
            "used_quota",
            "daily_remaining",
            "daily_limit",
            "url",
        ],
        [
            saved_at,
            result["status"],
            result["detail"],
            numbers.get("total_quota", ""),
            numbers.get("used_quota", ""),
            numbers.get("daily_remaining", ""),
            numbers.get("daily_limit", ""),
            page_url,
        ],
    )

    return text_path, csv_path


def classify_checkin_text(text):
    numbers = parse_checkin_numbers(text)

    if "签到成功" in text or "领取成功" in text or "发放成功" in text:
        return {
            "status": "success",
            "detail": "签到成功",
            "numbers": numbers,
        }
    if "今日已签到" in text or "已签到" in text:
        return {
            "status": "already_done",
            "detail": "今日已签到",
            "numbers": numbers,
        }
    if "今日全站额度已发完" in text or "全站额度已发完" in text:
        return {
            "status": "unavailable",
            "detail": "今日全站额度已发完",
            "numbers": numbers,
        }
    if "请明天再来" in text:
        return {
            "status": "unavailable",
            "detail": "请明天再来",
            "numbers": numbers,
        }
    if "请先登录" in text or "未登录" in text or "登录" in text and "个人中心" not in text:
        return {
            "status": "not_logged_in",
            "detail": "页面可能未登录",
            "numbers": numbers,
        }

    return None


def click_checkin_button(page, timeout_ms=2500):
    button_names = re.compile(r"(签到|领取|领取额度|每日签到|今日签到)", re.I)
    candidates = [
        lambda: page.get_by_role("button", name=button_names),
        lambda: page.locator("button").filter(has_text=button_names),
        lambda: page.locator("[role='button']").filter(has_text=button_names),
        lambda: page.get_by_text(button_names),
    ]

    for candidate in candidates:
        try:
            element = first_visible(candidate())
            if element is None:
                continue
            element.scroll_into_view_if_needed(timeout=1500)
            if hasattr(element, "is_enabled") and not element.is_enabled(timeout=1000):
                continue
            element.click(timeout=timeout_ms)
            return True
        except Exception:
            continue

    try:
        return click_text_or_clickable_ancestor(page, ["签到", "领取额度", "领取"])
    except Exception:
        return False


def wait_for_checkin_result(page, timeout_seconds, previous_text=None):
    deadline = time.monotonic() + timeout_seconds
    started_at = time.monotonic()
    last_text = previous_text or ""

    while time.monotonic() < deadline:
        command = read_wait_command()
        if command == "quit":
            raise ActivationWaitCancelled("User requested exit while waiting for check-in result.")

        text = page_text(page)
        result = classify_checkin_text(text)
        if result:
            if previous_text is not None and text == previous_text and time.monotonic() - started_at < 2:
                time.sleep(0.5)
                continue
            return result

        if text != last_text and ("每日签到" in text or "个人中心" in text):
            last_text = text

        time.sleep(0.5)

    numbers = parse_checkin_numbers(last_text or page_text(page))
    return {
        "status": "unknown",
        "detail": "等待签到结果超时",
        "numbers": numbers,
    }


def run_daily_checkin(page, args):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass

    time.sleep(args.checkin_delay)
    text = page_text(page)
    initial_result = classify_checkin_text(text)
    if initial_result and initial_result["status"] in {"unavailable", "already_done"}:
        text_path, csv_path = append_checkin_result(args, initial_result, page.url)
        print(f"Daily check-in status: {initial_result['detail']}")
        print(f"Text: {text_path}")
        print(f"CSV: {csv_path}")
        return initial_result

    if "个人中心" not in text and "每日签到" not in text and "签到" not in text:
        result = {
            "status": "not_ready",
            "detail": "没有检测到个人中心或每日签到区域，请确认登录状态和页面地址",
            "numbers": parse_checkin_numbers(text),
        }
        text_path, csv_path = append_checkin_result(args, result, page.url)
        print(result["detail"])
        print(f"Text: {text_path}")
        print(f"CSV: {csv_path}")
        return result

    print("Trying daily check-in...")
    print("While waiting: press Q to quit.")
    if not click_checkin_button(page):
        result = {
            "status": "no_button",
            "detail": "没有找到可点击的签到按钮",
            "numbers": parse_checkin_numbers(text),
        }
        text_path, csv_path = append_checkin_result(args, result, page.url)
        print(result["detail"])
        print(f"Text: {text_path}")
        print(f"CSV: {csv_path}")
        return result

    try:
        result = wait_for_checkin_result(page, args.checkin_timeout, text)
    except ActivationWaitCancelled as exc:
        result = {
            "status": "stopped",
            "detail": str(exc),
            "numbers": parse_checkin_numbers(page_text(page)),
        }

    text_path, csv_path = append_checkin_result(args, result, page.url)
    print(f"Daily check-in status: {result['status']} - {result['detail']}")
    print(f"Text: {text_path}")
    print(f"CSV: {csv_path}")
    return result


def wait_before_close(args):
    if not args.no_close_wait:
        input("Press Enter here to close the browser...")


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
        "--add-member-keys",
        action="store_true",
        help="Open the backpack page and bulk add API keys as member keys.",
    )
    parser.add_argument(
        "--donate-keys",
        action="store_true",
        help="Open the lottery page and donate stored API keys.",
    )
    parser.add_argument(
        "--query-usage",
        action="store_true",
        help="Open the usage page and query stored API key capacity/usage.",
    )
    parser.add_argument(
        "--check-in",
        action="store_true",
        help="Open the personal center page and run daily check-in.",
    )
    parser.add_argument(
        "--checkin-url",
        default=DEFAULT_CHECKIN_URL,
        help="Personal center page URL used by --check-in.",
    )
    parser.add_argument(
        "--checkin-log-file",
        default="checkin_log.txt",
        help="Text result log used by --check-in.",
    )
    parser.add_argument(
        "--checkin-csv-file",
        default="checkin_log.csv",
        help="CSV result log used by --check-in.",
    )
    parser.add_argument(
        "--checkin-timeout",
        type=int,
        default=20,
        help="Seconds to wait for daily check-in result.",
    )
    parser.add_argument(
        "--checkin-delay",
        type=float,
        default=1.0,
        help="Seconds to wait after opening the personal center page before checking status.",
    )
    parser.add_argument(
        "--usage-url",
        default=DEFAULT_USAGE_URL,
        help="Usage query page URL used by --query-usage.",
    )
    parser.add_argument(
        "--usage-keys-file",
        default="activation_keys.txt",
        help="File containing sk-jb API keys for --query-usage.",
    )
    parser.add_argument(
        "--usage-results-file",
        default="usage_results.txt",
        help="Text result file used by --query-usage.",
    )
    parser.add_argument(
        "--usage-csv-file",
        default="usage_results.csv",
        help="CSV result file used by --query-usage.",
    )
    parser.add_argument(
        "--usage-timeout",
        type=int,
        default=15,
        help="Seconds to wait for each usage query result.",
    )
    parser.add_argument(
        "--usage-delay",
        type=float,
        default=0.8,
        help="Seconds to wait after clicking each usage query button before checking the result.",
    )
    parser.add_argument(
        "--donation-url",
        default=DEFAULT_DONATION_URL,
        help="Lottery page URL used by --donate-keys.",
    )
    parser.add_argument(
        "--donation-keys-file",
        default="activation_keys.txt",
        help="File containing sk-jb API keys for --donate-keys.",
    )
    parser.add_argument(
        "--donation-state-file",
        default="donation_progress.json",
        help="JSON progress file used by --donate-keys.",
    )
    parser.add_argument(
        "--donation-results-file",
        default="donation_results.csv",
        help="CSV result log used by --donate-keys.",
    )
    parser.add_argument(
        "--donation-restart",
        action="store_true",
        help="Start donating from the first key instead of resuming saved progress.",
    )
    parser.add_argument(
        "--donation-start-index",
        type=int,
        help="Start donating from this 1-based key number.",
    )
    parser.add_argument(
        "--donation-timeout",
        type=int,
        default=20,
        help="Seconds to wait for each donation result.",
    )
    parser.add_argument(
        "--donation-delay",
        type=float,
        default=0.8,
        help="Seconds to wait after each donation attempt.",
    )
    parser.add_argument(
        "--cycle-member-keys",
        action="store_true",
        help="Deprecated alias for --add-member-keys. It adds keys only and does not delete member keys.",
    )
    parser.add_argument(
        "--backpack-url",
        default=DEFAULT_BACKPACK_URL,
        help="Backpack page URL used by --add-member-keys.",
    )
    parser.add_argument(
        "--member-keys-file",
        default="activation_keys.txt",
        help="File containing sk-jb API keys for --add-member-keys.",
    )
    parser.add_argument(
        "--delete-after-add",
        action="store_true",
        help="Deprecated and ignored for safety. Member keys are never deleted by this script.",
    )
    parser.add_argument(
        "--member-key-timeout",
        type=int,
        default=15,
        help="Seconds to wait for each member key add result.",
    )
    parser.add_argument(
        "--member-key-delay",
        type=float,
        default=0.8,
        help="Seconds to wait after each member key operation.",
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
        "--no-close-wait",
        action="store_true",
        help="Close the browser automatically when the selected mode finishes.",
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

    if args.cycle_member_keys:
        args.add_member_keys = True

    if args.donate_keys:
        credentials = []
        member_keys = []
        member_keys_path = None
        donation_keys, donation_keys_path = load_api_keys(args.donation_keys_file)
        usage_keys = []
        usage_keys_path = None
    elif args.check_in:
        credentials = []
        member_keys = []
        member_keys_path = None
        donation_keys = []
        donation_keys_path = None
        usage_keys = []
        usage_keys_path = None
    elif args.query_usage:
        credentials = []
        member_keys = []
        member_keys_path = None
        donation_keys = []
        donation_keys_path = None
        usage_keys, usage_keys_path = load_api_keys(args.usage_keys_file)
    elif args.add_member_keys:
        credentials = []
        member_keys, member_keys_path = load_api_keys(args.member_keys_file)
        donation_keys = []
        donation_keys_path = None
        usage_keys = []
        usage_keys_path = None
    else:
        credentials = collect_credentials(args)
        member_keys = []
        member_keys_path = None
        donation_keys = []
        donation_keys_path = None
        usage_keys = []
        usage_keys_path = None

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

        if args.donate_keys:
            target_url = args.donation_url
        elif args.check_in:
            target_url = args.checkin_url
        elif args.query_usage:
            target_url = args.usage_url
        elif args.add_member_keys:
            target_url = args.backpack_url
        else:
            target_url = args.url
        page = open_target_page(context, target_url, args.keep_extra_tabs)
        if not args.no_start_wait:
            if args.donate_keys:
                wait_for_key(
                    "Lottery page opened. Log in and confirm the page is ready, then press Enter here to start donating keys..."
                )
            elif args.check_in:
                wait_for_key(
                    "Personal center opened. Log in and confirm the page is ready, then press Enter here to run daily check-in..."
                )
            elif args.query_usage:
                wait_for_key(
                    "Usage query page opened. Log in and confirm the page is ready, then press Enter here to start querying key usage..."
                )
            elif args.add_member_keys:
                wait_for_key(
                    "Backpack page opened. Log in and confirm the backpack page is ready, then press Enter here to start adding member keys..."
                )
            else:
                wait_for_key(
                    "Browser opened. Log in or navigate to the target page first, then press Enter here to start..."
                )

        if args.donate_keys:
            print(f"Reading donation keys from: {donation_keys_path}")
            donate_keys(page, donation_keys, donation_keys_path, args)
            wait_before_close(args)
            context.close()
            return

        if args.check_in:
            run_daily_checkin(page, args)
            wait_before_close(args)
            context.close()
            return

        if args.query_usage:
            print(f"Reading usage query keys from: {usage_keys_path}")
            query_key_usage(page, usage_keys, usage_keys_path, args)
            wait_before_close(args)
            context.close()
            return

        if args.add_member_keys:
            print(f"Reading member keys from: {member_keys_path}")
            add_member_keys(page, member_keys, args)
            wait_before_close(args)
            context.close()
            return

        total = len(credentials)
        should_exit = False
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
                print("While waiting: press Q to quit, or S to skip this account.")
                try:
                    api_key, log_excerpt = wait_for_activation_result(
                        page,
                        previous_keys,
                        args.activation_timeout,
                        args.poll_interval,
                    )
                except ActivationWaitSkipped as exc:
                    print(f"{exc} Moving to the next account.")
                    if index < total:
                        page.goto(args.url, wait_until="domcontentloaded")
                    continue
                except ActivationWaitCancelled as exc:
                    print(exc)
                    should_exit = True
                    break

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

        if not should_exit:
            wait_before_close(args)
        context.close()


if __name__ == "__main__":
    main()
