"""Measure DistilBERT category-classification + routing accuracy on a labeled set."""
import asyncio, os, sys, time
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.classifier import ClassifierService, RESOLUTION_RULES

# (title, description, expected_category)
TESTS = [
    ("Cannot connect to VPN", "My VPN client times out right after I enter my password since this morning", "VPN"),
    ("VPN keeps dropping", "The corporate VPN disconnects every few minutes when I work from home", "VPN"),
    ("Forgot my password", "I am locked out of my account and need to reset my password, the reset email never arrives", "Password_Reset"),
    ("Account locked", "Too many login attempts locked my account and I cannot sign in", "Password_Reset"),
    ("Laptop won't turn on", "My laptop is completely dead, no lights even with a different charger", "Hardware"),
    ("Broken keyboard", "Several keys on my laptop keyboard have stopped working physically", "Hardware"),
    ("Need software installed", "Please install Zoom on my work laptop for a client meeting tomorrow", "Software_Install"),
    ("Install Photoshop", "I need Adobe Photoshop installed on my workstation for the design team", "Software_Install"),
    ("Payroll error", "My last paycheck was short by two days of pay, can payroll check the calculation", "Payroll"),
    ("Missing salary", "I did not receive my salary deposit this month, it is overdue", "Payroll"),
    ("Office WiFi down", "The whole office wifi keeps dropping for everyone on floor 3 since lunch", "Network"),
    ("No internet", "I have no network connectivity at my desk, ethernet and wifi both fail", "Network"),
    ("Suspicious login", "I think my account was hacked, there are logins from a country I have never visited", "Security"),
    ("Phishing email", "I received a phishing email asking for my credentials and may have clicked it", "Security"),
    ("Outlook not syncing", "My Outlook stopped receiving new emails this morning and says disconnected", "Email"),
    ("Cannot send email", "Every email I try to send bounces back with an SMTP error", "Email"),
    ("Printer paper jam", "The floor 2 printer shows a paper jam error but there is no jam and nobody can print", "Printer"),
    ("Printer offline", "Our shared printer shows offline and will not accept any print jobs", "Printer"),
    ("Need folder access", "I need access to the shared finance folder for my new role in accounting", "Access_Request"),
    ("Permission to system", "Please grant me access to the CRM system, I cannot open it", "Access_Request"),
    ("Recover deleted files", "I accidentally deleted an important project folder and need it recovered", "Data_Recovery"),
    ("Lost documents", "My documents were wiped after a crash, can they be restored from backup", "Data_Recovery"),
    ("Computer very slow", "My laptop is extremely slow and freezes whenever I open more than two apps", "Performance"),
    ("System lagging", "Everything lags badly, applications take minutes to respond", "Performance"),
    ("New employee setup", "We have a new hire starting Monday who needs accounts and equipment set up", "Onboarding"),
    ("Onboard new staff", "Please provision a laptop, email and system access for our new analyst", "Onboarding"),
    ("Employee leaving", "An employee is leaving Friday, please disable all of their system accounts", "Offboarding"),
    ("Deactivate accounts", "Offboard a departing team member and revoke all their access", "Offboarding"),
    ("Compliance audit", "We need documentation for the upcoming compliance audit on data handling", "Compliance"),
    ("GDPR request", "A customer submitted a GDPR data deletion request we must process for compliance", "Compliance"),
    ("OneDrive full", "My OneDrive storage is full and will not sync any more files", "Cloud_Storage"),
    ("Cloud access denied", "I cannot access our SharePoint cloud storage, it says quota exceeded", "Cloud_Storage"),
    ("Phone won't enroll", "My company mobile device will not enroll in MDM and apps won't push", "Mobile_Device"),
    ("Tablet issue", "My work tablet is not receiving the configuration profiles from device management", "Mobile_Device"),
    ("Database errors", "The customer database returns errors when we run the daily sales report", "Database"),
    ("DB connection failed", "Our application cannot connect to the SQL database, connection refused", "Database"),
    ("App crashes", "The internal expense application crashes every time I open the reports tab", "Application_Error"),
    ("Software error", "I keep getting an unexpected error code when saving in the inventory app", "Application_Error"),
    ("Charged twice", "I was charged twice for my software subscription and need a refund for the duplicate", "Billing"),
    ("Wrong invoice", "My invoice this month shows the wrong amount, I was overcharged", "Billing"),
]


# Harder: less keyword-obvious phrasing, real-user wording.
HARD_TESTS = [
    ("Kicked off remotely", "I keep getting kicked off the system every few minutes when working from home", "VPN"),
    ("Nothing on power", "Nothing happens at all when I press the power button on my machine", "Hardware"),
    ("Credentials expired", "The screen says my credentials have expired and won't let me in", "Password_Reset"),
    ("Boots very slowly", "My machine takes about 10 minutes to boot up lately and stutters", "Performance"),
    ("Not getting messages", "People say they emailed me but nothing is arriving in my inbox", "Email"),
    ("Files vanished", "Documents I saved to my work folder yesterday have completely vanished", "Data_Recovery"),
    ("Double charge", "Two separate charges appeared on our account for a single license", "Billing"),
    ("Setting up newcomer", "Setting up a workstation and logins for someone joining us next week", "Onboarding"),
    ("Access denied to files", "I can see the shared drive but get access denied when I open the files", "Access_Request"),
    ("Reports error out", "Reports just spin forever and then throw an error when I generate them", "Application_Error"),
    ("Cant reach server db", "Our app says it cannot reach the server and the connection is refused", "Database"),
    ("Quota exceeded sync", "My cloud files stopped syncing and it says I am over my storage quota", "Cloud_Storage"),
]


async def run_set(clf, name, tests):
    from services.classifier import RESOLUTION_RULES
    cat_ok = route_ok = 0
    misses = []
    for title, desc, exp in tests:
        res = await clf.classify(title, desc)
        if res.category == exp:
            cat_ok += 1
        else:
            misses.append((title, exp, res.category, round(res.confidence, 2)))
        if RESOLUTION_RULES.get(res.category) == RESOLUTION_RULES.get(exp):
            route_ok += 1
    n = len(tests)
    print(f"\n== {name}: {n} tickets ==")
    print(f"Exact category accuracy : {cat_ok}/{n} = {100*cat_ok/n:.1f}%")
    print(f"Routing-class accuracy  : {route_ok}/{n} = {100*route_ok/n:.1f}%")
    if misses:
        print("Misses (expected -> predicted | conf):")
        for t, e, p, c in misses:
            print(f"  - {t!r}: {e} -> {p} ({c})")


async def main():
    clf = ClassifierService()
    await clf.load()
    print(f"DistilBERT loaded: {clf._model_loaded} (device={clf.device})\n")

    await run_set(clf, "CLEAR cases", TESTS)
    await run_set(clf, "HARD cases", HARD_TESTS)
    return

    cat_ok = route_ok = 0
    times = []
    models = {}
    misses = []
    for title, desc, exp in TESTS:
        t0 = time.perf_counter()
        res = await clf.classify(title, desc)
        times.append((time.perf_counter() - t0) * 1000)
        models[res.model_used] = models.get(res.model_used, 0) + 1
        if res.category == exp:
            cat_ok += 1
        else:
            misses.append((title, exp, res.category, round(res.confidence, 2)))
        # routing-class correctness: predicted category's class vs expected class
        if RESOLUTION_RULES.get(res.category) == RESOLUTION_RULES.get(exp):
            route_ok += 1

    n = len(TESTS)
    print(f"== RESULTS over {n} labeled tickets ==")
    print(f"Exact category accuracy : {cat_ok}/{n} = {100*cat_ok/n:.1f}%")
    print(f"Routing-class accuracy  : {route_ok}/{n} = {100*route_ok/n:.1f}%")
    print(f"Avg classify latency    : {sum(times)/len(times):.1f} ms  (max {max(times):.0f} ms)")
    print(f"Model used              : {models}")
    if misses:
        print("\nMisclassifications (title | expected -> predicted | conf):")
        for t, e, p, c in misses:
            print(f"  - {t!r}: {e} -> {p} ({c})")


asyncio.run(main())
