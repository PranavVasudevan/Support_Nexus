#!/usr/bin/env python3
"""
Realistic IT-support ticket dataset generator (pure standard library).

Why this exists
---------------
The original `massive_ticket_dataset_200k.csv` leaked the label: every title
literally began with the category name ("VPN issue with ...") while the
description was random text unrelated to the category. A model trained on it
learns to read the leaked title token, not the actual problem — so it fails on
real user phrasing ("I can't connect from home and it times out").

This generator instead writes tickets whose **title and description genuinely
describe the problem** using the natural vocabulary a real user would type. The
category name is never injected as a leak; the signal is the symptom language
itself ("times out at authentication", "stuck in my outbox", "locked out").

Output (written to ../data):
    ticket_train.csv   (default 100,000 rows  → "1 lakh")
    ticket_val.csv     (default  15,000 rows)
    ticket_test.csv    (default  15,000 rows)
    dataset_metadata.json

Usage:
    python scripts/generate_dataset.py
    python scripts/generate_dataset.py --train 100000 --val 15000 --test 15000
"""
import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42

CATEGORIES = [
    "VPN", "Password_Reset", "Hardware", "Software_Install", "Payroll",
    "Network", "Security", "Email", "Printer", "Access_Request",
    "Data_Recovery", "Performance", "Onboarding", "Offboarding",
    "Compliance", "Cloud_Storage", "Mobile_Device", "Database",
    "Application_Error", "Billing",
]

RESOLUTION_RULES = {
    "Password_Reset": "autonomous", "Email": "autonomous", "Printer": "autonomous",
    "Cloud_Storage": "autonomous", "VPN": "autonomous", "Software_Install": "autonomous",
    "Mobile_Device": "autonomous", "Performance": "autonomous",
    "Data_Recovery": "hitl", "Database": "hitl", "Hardware": "hitl", "Network": "hitl",
    "Access_Request": "hitl", "Onboarding": "hitl", "Application_Error": "hitl",
    "Payroll": "human", "Security": "human", "Compliance": "human",
    "Offboarding": "human", "Billing": "human",
}

# Per-category natural-language content. titles + descriptions both describe the
# real symptom; no category label is injected verbatim.
CONTENT = {
    "VPN": {
        "titles": ["Can't connect to VPN", "VPN keeps disconnecting", "VPN authentication failing",
                   "Remote VPN access not working", "VPN is very slow", "VPN won't establish a tunnel",
                   "Unable to work remotely over VPN", "VPN drops every few minutes"],
        "desc": ["I'm unable to connect to the company VPN from home and it times out at authentication.",
                 "The VPN tunnel drops every few minutes and I lose access to internal apps.",
                 "The VPN client says authentication failed even though my password is correct.",
                 "I can't reach internal servers because the VPN won't establish a connection.",
                 "VPN connects but is extremely slow when I open shared drives remotely.",
                 "Working from home and the VPN keeps disconnecting, I can't stay logged in.",
                 "The remote access client gets stuck on connecting and never finishes.",
                 "After the update my VPN profile no longer connects to the gateway."],
    },
    "Password_Reset": {
        "titles": ["Forgot my password", "Account locked out", "Need a password reset",
                   "Can't log in to my account", "Password expired", "Locked out after failed logins",
                   "Reset my login credentials", "Can't sign in this morning"],
        "desc": ["I forgot my password and can't sign in to my workstation this morning.",
                 "My account is locked after too many login attempts, please reset it.",
                 "I need to reset my password because the old one no longer works.",
                 "I'm locked out of my account and need a password reset to get back in.",
                 "My password expired over the weekend and the self-service reset isn't working.",
                 "I keep getting 'invalid credentials' and now my account is locked.",
                 "Can someone reset my login? I can't remember my current password.",
                 "I've been locked out and the reset email never arrived."],
    },
    "Hardware": {
        "titles": ["Laptop won't turn on", "Monitor not displaying", "Keyboard not working",
                   "Laptop overheating", "Docking station issue", "Battery not charging",
                   "Mouse stopped responding", "Screen flickering"],
        "desc": ["My laptop won't power on at all, there are no lights when I press the button.",
                 "My external monitor shows no signal even though it's plugged in correctly.",
                 "Several keys on my keyboard have stopped responding entirely.",
                 "My laptop overheats and shuts itself down randomly during work.",
                 "The docking station no longer charges my laptop or connects my peripherals.",
                 "My battery won't charge past zero even when plugged into the adapter.",
                 "My wireless mouse suddenly stopped working and a new battery didn't help.",
                 "My display keeps flickering and occasionally goes black for a second."],
    },
    "Software_Install": {
        "titles": ["Need software installed", "Installation keeps failing", "Request app installation",
                   "Can't install application", "Software license needed", "Missing required program",
                   "Install design tool", "Need admin rights to install"],
        "desc": ["I need the design software installed on my work machine, please push it to me.",
                 "The installer keeps failing with an error about halfway through.",
                 "Requesting installation of the project management application for my team.",
                 "I don't have admin rights to install the tool I need for my daily work.",
                 "I need a license and installation of the analytics application.",
                 "Please deploy the new client software to my laptop, I don't have it yet.",
                 "The setup file won't run and asks for permissions I don't have.",
                 "Can you install the latest version of the app I use? Mine is outdated."],
    },
    "Payroll": {
        "titles": ["Payslip amount is incorrect", "Salary not credited", "Tax deduction looks wrong",
                   "Missing overtime pay", "Payroll query", "Bonus not paid", "Wrong bank details on pay",
                   "Deduction I don't recognise"],
        "desc": ["My latest payslip shows the wrong amount and my salary seems short this month.",
                 "My salary hasn't been credited to my bank account this pay cycle.",
                 "The tax deducted from my pay looks incorrect compared to last month.",
                 "My overtime hours are missing from this month's pay.",
                 "I have a question about a deduction that appeared on my payroll statement.",
                 "My performance bonus wasn't included in this month's payment.",
                 "My pay went to the wrong account, the bank details on file are outdated.",
                 "There's a deduction on my payslip I don't recognise and want explained."],
    },
    "Network": {
        "titles": ["No internet connection", "WiFi keeps dropping", "Network is very slow",
                   "Can't reach internal sites", "Ethernet not working", "Office connectivity down",
                   "Intermittent connection", "DNS resolution failing"],
        "desc": ["There's no internet connectivity at my desk since this morning.",
                 "The office WiFi keeps dropping every few minutes and I have to reconnect.",
                 "The network is extremely slow and pages take forever to load today.",
                 "I can't reach internal websites though external sites load fine.",
                 "My wired ethernet shows connected but there's no actual internet access.",
                 "Connectivity in our area of the office seems to be completely down.",
                 "My connection keeps dropping intermittently throughout the day.",
                 "Some sites won't resolve at all, looks like a DNS problem."],
    },
    "Security": {
        "titles": ["Suspicious email received", "Possible phishing attempt", "Account may be hacked",
                   "Malware warning on laptop", "Report a security incident", "Clicked a suspicious link",
                   "Unrecognised account activity", "Antivirus alert"],
        "desc": ["I received a suspicious email asking for my credentials, it looks like phishing.",
                 "I think my account was compromised, there's activity I don't recognise.",
                 "My antivirus is flagging a possible malware infection on my laptop.",
                 "I clicked a suspicious link and now I'm worried about a security breach.",
                 "I want to report a potential security incident involving my device.",
                 "There were login attempts from a location I've never been to.",
                 "A colleague got a fake email pretending to be from our CEO asking for gift cards.",
                 "My machine is showing pop-ups and the antivirus keeps alerting."],
    },
    "Email": {
        "titles": ["Can't send emails", "Outlook not syncing", "Mailbox is full",
                   "Not receiving emails", "Emails stuck in outbox", "Outlook keeps asking for password",
                   "Calendar not syncing", "Can't open attachments"],
        "desc": ["I'm unable to send emails, they just get stuck in my outbox.",
                 "Outlook isn't syncing and I can't see any new messages.",
                 "My mailbox is full and I can't receive any new emails.",
                 "I stopped receiving emails since yesterday afternoon.",
                 "Emails sit in the outbox and never actually send out.",
                 "Outlook keeps prompting me for my password in a loop.",
                 "My calendar events aren't syncing across my devices.",
                 "I can't open attachments, they fail to download in my mail client."],
    },
    "Printer": {
        "titles": ["Printer not printing", "Print jobs stuck in queue", "Can't connect to printer",
                   "Printer shows offline", "Scanner not working", "Printer printing blank pages",
                   "Paper jam won't clear", "Can't add network printer"],
        "desc": ["The printer won't print anything, my jobs just sit there with no output.",
                 "Print jobs are stuck in the queue and nothing ever comes out.",
                 "I can't connect to the office printer from my laptop.",
                 "The printer shows as offline even though it's powered on and online.",
                 "The scanner part of the printer isn't responding when I try to scan.",
                 "The printer pushes out blank pages instead of my document.",
                 "There's a paper jam message that won't clear even after checking the trays.",
                 "I can't add the network printer, it isn't showing up in my list."],
    },
    "Access_Request": {
        "titles": ["Need access to shared folder", "Request system access", "Permission denied to app",
                   "Need access to a drive", "Role-based access request", "Access to reporting tool",
                   "Can't open a restricted file", "Request group membership"],
        "desc": ["I need access to the shared finance folder for my new project.",
                 "Requesting access to the internal reporting system for my role.",
                 "I'm getting 'permission denied' when opening the application I need.",
                 "Please grant me access to the team's shared network drive.",
                 "I need elevated access permissions to perform my job duties.",
                 "I can't open a file because I'm not in the right access group.",
                 "Please add me to the project distribution and access group.",
                 "I moved teams and need access to my new department's systems."],
    },
    "Data_Recovery": {
        "titles": ["Deleted an important file", "Need to restore data", "Lost files after crash",
                   "Recover overwritten document", "Restore from backup", "Files missing from folder",
                   "Recover deleted folder", "Corrupted file recovery"],
        "desc": ["I accidentally deleted an important file and need it recovered.",
                 "My documents are gone after a system crash, can they be restored?",
                 "I overwrote a document by mistake and need the previous version back.",
                 "I lost a whole folder of work files and need them recovered from backup.",
                 "Please restore my data from the latest backup, I lost everything locally.",
                 "A shared folder's files have vanished and we need them back.",
                 "I emptied the recycle bin too soon and need a deleted folder recovered.",
                 "One of my files is corrupted and won't open, can it be recovered?"],
    },
    "Performance": {
        "titles": ["Computer running very slow", "System keeps freezing", "High CPU usage",
                   "Laptop is sluggish", "Apps slow to open", "Constant lag and stutter",
                   "Machine takes ages to boot", "Everything is unresponsive"],
        "desc": ["My computer has become extremely slow over the past few days.",
                 "The system keeps freezing and I have to restart it constantly.",
                 "My CPU usage is always maxed out and everything lags badly.",
                 "My laptop is very sluggish and takes ages to do anything.",
                 "Applications take a very long time to open and respond.",
                 "There's constant lag and stutter even with just a browser open.",
                 "My machine takes ten minutes just to finish booting up.",
                 "Everything is unresponsive and the fan runs at full speed."],
    },
    "Onboarding": {
        "titles": ["New employee setup", "Onboard a new hire", "Accounts for new joiner",
                   "New starter equipment", "Onboarding access setup", "Provision new team member",
                   "First-day IT setup", "New hire laptop and logins"],
        "desc": ["We have a new employee starting Monday who needs accounts and equipment set up.",
                 "Please onboard our new hire with email, a laptop, and system access.",
                 "A new joiner needs all their accounts created before their first day.",
                 "Our new starter requires a laptop and the standard software provisioned.",
                 "Setting up a new team member who needs access to our core tools.",
                 "Please prepare IT access and hardware for a colleague joining next week.",
                 "New employee needs their logins, mailbox, and group memberships created.",
                 "Requesting full first-day setup for a new hire in our department."],
    },
    "Offboarding": {
        "titles": ["Employee is leaving", "Offboard departing staff", "Revoke access for a leaver",
                   "Disable departing employee account", "Exit IT tasks", "Deactivate leaver accounts",
                   "Recover equipment from leaver", "Last-day access removal"],
        "desc": ["An employee is leaving this week, please revoke all of their access.",
                 "We need to offboard a departing staff member and disable their accounts.",
                 "Please disable the account of an employee who has resigned.",
                 "Revoke all system access for a team member whose last day is Friday.",
                 "Need to complete the IT exit checklist for a departing employee.",
                 "A colleague is leaving; please deactivate their logins and mailbox.",
                 "We need to collect equipment and remove access for a leaver.",
                 "Disable accounts and forward email for an employee who left today."],
    },
    "Compliance": {
        "titles": ["Compliance audit request", "Data retention query", "GDPR data request",
                   "Policy compliance question", "Audit log request", "Regulatory review support",
                   "Data subject access request", "Retention policy clarification"],
        "desc": ["We have a compliance audit coming up and need access logs for review.",
                 "I have a question about our data retention policy for compliance purposes.",
                 "There's a GDPR data subject request that we need to action.",
                 "Need to confirm our setup meets the relevant compliance policy requirements.",
                 "Requesting audit logs for an upcoming regulatory compliance review.",
                 "We must provide records for an external auditor, what's the process?",
                 "A customer submitted a data access request we need to fulfil legally.",
                 "Please clarify how long we are required to retain these records."],
    },
    "Cloud_Storage": {
        "titles": ["OneDrive not syncing", "Cloud storage is full", "Can't access cloud files",
                   "SharePoint sync error", "Drive quota exceeded", "Files won't upload to cloud",
                   "Shared library access issue", "Cloud sync stuck"],
        "desc": ["My OneDrive stopped syncing and my files are now out of date.",
                 "My cloud storage is full and I can't save anything new.",
                 "I can't access my files in the cloud, it says access denied.",
                 "SharePoint keeps throwing a sync error on my documents.",
                 "I've exceeded my drive quota and need more space allocated.",
                 "Files won't upload to the cloud, they get stuck at zero percent.",
                 "I lost access to a shared cloud library I use every day.",
                 "The cloud sync is stuck and a green tick never appears on my files."],
    },
    "Mobile_Device": {
        "titles": ["Work phone not syncing", "Can't set up email on phone", "Device enrollment issue",
                   "Tablet not connecting", "Phone management error", "Corporate apps missing on phone",
                   "Can't access work apps on mobile", "Phone won't update policies"],
        "desc": ["My work phone won't sync company email and calendar anymore.",
                 "I can't set up my corporate email on my new phone.",
                 "My mobile device won't enroll in the management system.",
                 "My work tablet won't connect to company resources.",
                 "My phone keeps prompting a management error and won't update its policies.",
                 "The corporate apps disappeared from my phone after a restart.",
                 "I can't access any work apps on my mobile since the weekend.",
                 "My device says it's not compliant and blocks access to email."],
    },
    "Database": {
        "titles": ["Database connection error", "Can't connect to the database", "Database timing out",
                   "Queries running slow", "Lost database access", "DB login failing",
                   "Reports can't reach database", "Connection refused to DB"],
        "desc": ["My application can't connect to the database, it says connection refused.",
                 "I'm getting a database connection error whenever I run my reports.",
                 "The database keeps timing out when I try to query it.",
                 "Database queries are running extremely slowly today.",
                 "I've lost access to the database I use for my daily reports.",
                 "My database login is failing even with the correct credentials.",
                 "Our reporting tool can't reach the database backend this morning.",
                 "The connection to the data warehouse keeps dropping mid-query."],
    },
    "Application_Error": {
        "titles": ["App crashing on launch", "Application throwing errors", "Software keeps crashing",
                   "Error message in the app", "App won't open", "Unexpected error popup",
                   "Program freezes then closes", "App shows a blank screen"],
        "desc": ["The application crashes every single time I try to open it.",
                 "I keep getting an error message when I use the app.",
                 "The software crashes randomly while I'm in the middle of working.",
                 "An unexpected error pops up and then the app just closes.",
                 "The application won't open at all, it hangs and then quits.",
                 "I get an error code I don't understand whenever I save my work.",
                 "The program freezes for a moment and then disappears completely.",
                 "The app loads to a blank white screen and never shows content."],
    },
    "Billing": {
        "titles": ["Invoice query", "Billing discrepancy", "Subscription charge issue",
                   "Wrong amount billed", "License billing question", "Charged twice this month",
                   "Unexpected charge on bill", "Need a corrected invoice"],
        "desc": ["There's a discrepancy on our latest invoice that needs review.",
                 "We were billed the wrong amount for our software subscription.",
                 "I have a question about a charge on our billing statement.",
                 "Our subscription appears to have been charged twice this month.",
                 "I need clarification on the licensing costs shown on our bill.",
                 "An unexpected charge appeared on this month's invoice.",
                 "Please issue a corrected invoice, the current one is wrong.",
                 "We're being billed for seats we no longer use."],
    },
}

# Natural context sentences appended for lexical variety (category-neutral).
CONTEXTS = [
    "", "", "",  # weight towards no suffix
    "This started this morning.", "It began after the last update.",
    "It's blocking my work right now.", "Please help as soon as possible.",
    "A couple of colleagues have the same problem.", "Let me know what details you need.",
    "I've already tried restarting.", "This is fairly urgent for me.",
    "It worked fine yesterday.", "Happy to provide screenshots if useful.",
    "This has been happening on and off all week.", "I'm on a deadline so any help is appreciated.",
]

DEPARTMENTS = ["IT", "Finance", "Sales", "Marketing", "Engineering", "HR",
               "Operations", "Customer Support", "Product", "Legal"]
USER_ROLES = ["junior_employee", "senior_employee", "manager", "admin",
              "director", "executive", "contractor", "intern"]
PRIORITIES = ["low", "low", "medium", "medium", "medium", "high", "high", "critical"]


def _confidence_for(resolution: str, rng: random.Random) -> float:
    if resolution == "autonomous":
        return round(rng.uniform(0.90, 0.995), 4)
    if resolution == "hitl":
        return round(rng.uniform(0.78, 0.93), 4)
    return round(rng.uniform(0.55, 0.85), 4)


def _random_date(rng: random.Random) -> str:
    start = date(2023, 1, 1)
    end = date(2025, 12, 31)
    delta = (end - start).days
    return (start + timedelta(days=rng.randint(0, delta))).isoformat()


def generate_rows(n: int, start_id: int, rng: random.Random):
    rows = []
    per_cat = n // len(CATEGORIES)
    remainder = n - per_cat * len(CATEGORIES)
    tid = start_id
    plan = []
    for i, cat in enumerate(CATEGORIES):
        count = per_cat + (1 if i < remainder else 0)
        plan.extend([cat] * count)
    rng.shuffle(plan)

    for cat in plan:
        c = CONTENT[cat]
        title = rng.choice(c["titles"])
        desc = rng.choice(c["desc"])
        ctx = rng.choice(CONTEXTS)
        if ctx:
            desc = f"{desc} {ctx}"
        resolution = RESOLUTION_RULES[cat]
        rows.append({
            "ticket_id": f"TKT-{tid:07d}",
            "title": title,
            "description": desc,
            "category": cat,
            "priority": rng.choice(PRIORITIES),
            "department": rng.choice(DEPARTMENTS),
            "user_role": rng.choice(USER_ROLES),
            "resolution_type": resolution,
            "confidence_score": _confidence_for(resolution, rng),
            "created_date": _random_date(rng),
            "label": cat,
        })
        tid += 1
    return rows, tid


FIELDS = ["ticket_id", "title", "description", "category", "priority",
          "department", "user_role", "resolution_type", "confidence_score",
          "created_date", "label"]


def write_csv(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=100_000)
    ap.add_argument("--val",   type=int, default=15_000)
    ap.add_argument("--test",  type=int, default=15_000)
    ap.add_argument("--out",   default=str(Path(__file__).resolve().parent.parent / "data"))
    args = ap.parse_args()

    rng = random.Random(SEED)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tid = 1_000_000
    print(f"Generating {args.train:,} train rows...")
    train, tid = generate_rows(args.train, tid, rng)
    print(f"Generating {args.val:,} val rows...")
    val, tid = generate_rows(args.val, tid, rng)
    print(f"Generating {args.test:,} test rows...")
    test, tid = generate_rows(args.test, tid, rng)

    write_csv(out / "ticket_train.csv", train)
    write_csv(out / "ticket_val.csv", val)
    write_csv(out / "ticket_test.csv", test)

    meta = {
        "generator": "scripts/generate_dataset.py",
        "seed": SEED,
        "train_rows": len(train),
        "validation_rows": len(val),
        "test_rows": len(test),
        "total_rows": len(train) + len(val) + len(test),
        "num_categories": len(CATEGORIES),
        "categories": CATEGORIES,
        "features": FIELDS,
        "notes": "Realistic symptom-language tickets; category is NOT leaked into the "
                 "title/description. Balanced across all categories.",
    }
    with open(out / "dataset_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("\nDone. Wrote:")
    print(f"  {out / 'ticket_train.csv'}  ({len(train):,} rows)")
    print(f"  {out / 'ticket_val.csv'}    ({len(val):,} rows)")
    print(f"  {out / 'ticket_test.csv'}   ({len(test):,} rows)")
    print(f"  {out / 'dataset_metadata.json'}")


if __name__ == "__main__":
    main()
