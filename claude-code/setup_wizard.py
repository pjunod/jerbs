"""
setup_wizard.py — interactive first-time setup for jerbs (local daemon)
"""

import json
from pathlib import Path


def ask(prompt: str, default: str = "") -> str:
    display = f"{prompt}"
    if default:
        display += f" [{default}]"
    display += ": "
    val = input(display).strip()
    return val if val else default


def ask_list(prompt: str, examples: str = "") -> list:
    if examples:
        print(f"  Examples: {examples}")
    raw = input(f"{prompt} (comma-separated): ").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def ask_int(prompt: str, default: int) -> int:
    val = ask(prompt, str(default))
    try:
        return int(val)
    except ValueError:
        return default


def ask_bool(prompt: str, default: bool = False) -> bool:
    d = "y" if default else "n"
    val = ask(prompt + " (y/n)", d).lower()
    return val.startswith("y")


LINKEDIN_COOKIES_PATH = Path.home() / ".jerbs" / "linkedin_cookies.json"


def _save_linkedin_cookies(li_at: str, jsessionid: str) -> bool:
    """Save LinkedIn cookies and validate they work. Returns True on success."""
    LINKEDIN_COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LINKEDIN_COOKIES_PATH, "w") as f:
        json.dump({"li_at": li_at, "JSESSIONID": jsessionid}, f, indent=2)
    print(f"  Cookies saved to {LINKEDIN_COOKIES_PATH}")
    try:
        from linkedin_client import LinkedInClient

        client = LinkedInClient(send_mode=False, lookback_days=1)
        profile = client.api.get_user_profile()
        name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
        print(f"  Authenticated as: {name or 'OK'}")
        return True
    except Exception as e:
        print(f"  Warning: Cookie validation failed — {e}")
        print("  Cookies saved anyway; they may still work for messaging.")
        return True


def _try_browser_cookie3(browser: str) -> tuple[str, str] | None:
    """Try to extract LinkedIn cookies from the user's browser."""
    try:
        import browser_cookie3
    except ImportError:
        print("  browser_cookie3 not installed. Skipping auto-extract.")
        return None
    browser_funcs = {
        "chrome": browser_cookie3.chrome,
        "firefox": browser_cookie3.firefox,
        "safari": browser_cookie3.safari,
    }
    func = browser_funcs.get(browser.lower())
    if not func:
        print(f"  Unsupported browser: {browser}")
        return None
    try:
        cj = func(domain_name=".linkedin.com")
        li_at = None
        jsessionid = None
        for cookie in cj:
            if cookie.name == "li_at":
                li_at = cookie.value
            elif cookie.name == "JSESSIONID":
                jsessionid = cookie.value
        if li_at and jsessionid:
            return (li_at, jsessionid)
        print("  LinkedIn cookies not found in browser. Are you logged in?")
        return None
    except Exception as e:
        print(f"  Could not read browser cookies: {e}")
        return None


def _try_playwright_login() -> tuple[str, str] | None:
    """Open a Playwright browser for the user to log into LinkedIn."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed. Skipping browser login.")
        print("  Install with: pip install playwright && playwright install chromium")
        return None
    print("  Opening browser — please log into LinkedIn...")
    print("  (Close the browser window when you see your LinkedIn feed)")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://www.linkedin.com/login")
            page.wait_for_url("**/feed/**", timeout=300000)
            cookies = context.cookies()
            li_at = None
            jsessionid = None
            for c in cookies:
                if c["name"] == "li_at":
                    li_at = c["value"]
                elif c["name"] == "JSESSIONID":
                    jsessionid = c["value"]
            browser.close()
            if li_at and jsessionid:
                return (li_at, jsessionid)
            print("  Could not capture LinkedIn session cookies after login.")
            return None
    except Exception as e:
        print(f"  Playwright login failed: {e}")
        return None


def _setup_linkedin() -> bool:
    """Run the tiered LinkedIn auth flow. Returns True if cookies were saved."""
    browser = ask("Which browser are you logged into LinkedIn with?", "chrome")
    print(f"  Trying to extract cookies from {browser}...")
    result = _try_browser_cookie3(browser)
    if result:
        print("  Cookies extracted successfully!")
        return _save_linkedin_cookies(result[0], result[1])
    if ask_bool("  Open a browser window to log into LinkedIn?", True):
        result = _try_playwright_login()
        if result:
            print("  Cookies captured from browser login!")
            return _save_linkedin_cookies(result[0], result[1])
    print("\n  Manual cookie entry:")
    print("  1. Open LinkedIn in Chrome and log in")
    print("  2. Open DevTools (F12) → Application → Cookies → linkedin.com")
    print("  3. Copy the values for 'li_at' and 'JSESSIONID'\n")
    li_at = ask("  li_at cookie value")
    jsessionid = ask("  JSESSIONID cookie value")
    if li_at and jsessionid:
        return _save_linkedin_cookies(li_at, jsessionid)
    return False


def run_setup_wizard(output_path: Path):
    print("\n" + "─" * 55)
    print("  jerbs setup wizard")
    print("─" * 55)
    print("  Answer each section. Press Enter to accept defaults.\n")

    criteria = json.loads(
        (Path(__file__).parent.parent / "shared" / "criteria_template.json").read_text()
    )

    print("── Identity ──────────────────────────────────────────")
    criteria["identity"]["name"] = ask("Your name")
    criteria["identity"]["current_title"] = ask("Current title", "Software Engineer")
    criteria["identity"]["background_summary"] = ask(
        "Background summary", "Experienced software engineer targeting senior roles"
    )
    criteria["identity"]["seniority_level"] = ask(
        "Seniority level", "Senior and above — no junior, mid-level, or intern"
    )
    criteria["identity"]["target_roles"] = ask_list(
        "Target roles", "Senior SRE, Staff Engineer, Principal Engineer"
    )

    print("\n── Target companies ──────────────────────────────────")
    criteria["target_companies"]["industries"] = ask_list(
        "Target industries/company types",
        "FAANG-tier tech, fintech, crypto, HFT, high-signal startups",
    )
    criteria["target_companies"]["prestige_requirement"] = ask(
        "Prestige requirement", "Upper-tier only — no unknown companies"
    )
    criteria["target_companies"]["whitelist"] = ask_list(
        "Dream companies (always flag positively, optional)", "Google, Anthropic, OpenAI"
    )
    criteria["target_companies"]["blacklist"] = ask_list(
        "Companies to always ignore", "Deloitte, Accenture, random staffing agencies"
    )
    criteria["target_industries_blocklist"] = ask_list(
        "Industries to block entirely (optional)", "defense, tobacco, gambling, MLM"
    )

    print("\n── Role requirements ─────────────────────────────────")
    ft_only = ask_bool("Full-time only?", True)
    criteria["role_requirements"]["employment_type"] = (
        ["full-time"] if ft_only else ["full-time", "contract"]
    )
    criteria["role_requirements"]["remote_preference"] = ask(
        "Remote preference", "Depends on location — must be disclosed"
    )

    print("\n── Compensation ──────────────────────────────────────")
    criteria["compensation"]["base_salary_floor"] = ask_int("Minimum base salary ($)", 150000)
    criteria["compensation"]["base_salary_currency"] = ask("Currency", "USD")
    criteria["compensation"]["total_comp_target"] = ask_int("Target total comp ($)", 250000)
    criteria["compensation"]["equity_required"] = ask_bool("Equity required?", True)
    criteria["compensation"]["sliding_scale_notes"] = ask(
        "Any nuances to comp expectations (optional)",
        "Remote roles more flexible on base. In-office 3+ days expects higher base.",
    )

    print("\n── Tech stack ────────────────────────────────────────")
    criteria["tech_stack"]["required"] = ask_list("Required stack (optional)", "Linux servers")
    criteria["tech_stack"]["dealbreaker"] = ask_list(
        "Stack dealbreakers (optional)", "Windows OS, Windows servers"
    )
    criteria["tech_stack"]["preferred"] = ask_list("Preferred stack (optional)", "")

    print("\n── Hard dealbreakers ─────────────────────────────────")
    print("  Common defaults (press Enter to accept all):")
    defaults = [
        "Contract, part-time, freelance, consulting",
        "Junior, intern, associate, or mid-level role",
        "Salary top-of-range explicitly below base floor",
        "Generic/mass email with no personalization",
        "Completely unknown company with no pedigree or funding signal",
        "Staffing/recruiting agency for undisclosed client",
        "Company on personal blacklist",
    ]
    for d in defaults:
        print(f"  · {d}")
    use_defaults = ask_bool("\nUse these defaults?", True)
    criteria["hard_dealbreakers"] = defaults if use_defaults else []
    extras = ask_list("Any additional dealbreakers? (optional)", "")
    criteria["hard_dealbreakers"].extend(extras)

    print("\n── Required info ─────────────────────────────────────")
    req_defaults = [
        "Salary / compensation range (base + TC)",
        "Equity details (type, vesting)",
        "Remote / hybrid / in-office policy",
        "Number of in-office days if hybrid",
        "Interview process overview",
        "Company name (if obscured)",
    ]
    for r in req_defaults:
        print(f"  · {r}")
    use_req = ask_bool("\nUse these defaults?", True)
    criteria["required_info"] = req_defaults if use_req else []
    extra_req = ask_list("Any additional required fields? (optional)", "Nature of work, team size")
    criteria["required_info"].extend(extra_req)

    print("\n── Reply settings ────────────────────────────────────")
    criteria["reply_settings"]["tone"] = ask("Reply tone", "professional and direct")
    criteria["reply_settings"]["signature"] = ask("Sign off as", criteria["identity"]["name"] or "")

    print("\n── Business hours (for scheduler) ───────────────────")
    criteria["search_settings"]["timezone"] = ask("Timezone", "America/New_York")
    criteria["search_settings"]["biz_start_hour"] = ask_int("Business day start (24h hour)", 9)
    criteria["search_settings"]["biz_end_hour"] = ask_int("Business day end (24h hour)", 17)

    print("\n── LinkedIn DM screening (optional) ─────────────────")
    if ask_bool("Enable LinkedIn DM screening?", False):
        linkedin_cookies = _setup_linkedin()
        if linkedin_cookies:
            criteria["linkedin"] = {"enabled": True}
        else:
            print("  LinkedIn setup skipped — you can re-run --setup later.")
            criteria["linkedin"] = {"enabled": False}
    else:
        criteria["linkedin"] = {"enabled": False}

    criteria["profile_name"] = ask(
        "\nProfile name",
        f"{criteria['identity']['name']}'s Job Search"
        if criteria["identity"]["name"]
        else "My Job Search",
    )
    criteria["last_run_date"] = ""
    criteria["screened_message_ids"] = []

    print("\n" + "─" * 55)
    print("  Summary")
    print("─" * 55)
    print(f"  Name:       {criteria['identity']['name']}")
    print(f"  Base floor: ${criteria['compensation']['base_salary_floor']:,}")
    print(f"  TC target:  ${criteria['compensation']['total_comp_target']:,}+")
    print(
        f"  Biz hours:  {criteria['search_settings']['biz_start_hour']}:00–"
        f"{criteria['search_settings']['biz_end_hour']}:00 "
        f"({criteria['search_settings']['timezone']})"
    )
    print("─" * 55)

    confirm = ask_bool("\nSave this profile?", True)
    if not confirm:
        print("Setup cancelled — nothing saved.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(criteria, f, indent=2)

    print(f"\nProfile saved to {output_path}")
