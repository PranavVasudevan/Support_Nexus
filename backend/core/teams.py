"""
Department routing & access control.
═════════════════════════════════════
Five organisation departments each own a set of ticket categories. A
`department`-role user only ever sees tickets whose AI-assigned category is in
their set. Categories can be shared across departments (intentional handoffs,
e.g. Onboarding spans BASE + HR-GO + HR-BP).

Mapping per the Department_Routing_Concept spec.
"""

DEPARTMENT_NAMES = {
    "TSG":     "Tech Support Group",
    "BASE":    "Facilities (BASE)",
    "HR-GO":   "HR Global Operations",
    "HR-BP":   "HR Business Partner",
    "Finance": "Finance",
}

DEPARTMENTS = {
    # TSG — anything involving a device, system, or digital tool.
    "TSG": ["VPN", "Network", "Email", "Password_Reset", "Printer", "Software_Install",
            "Application_Error", "Performance", "Mobile_Device", "Hardware",
            "Database", "Cloud_Storage", "Security", "Data_Recovery", "Access_Request"],
    # BASE — the physical workplace (+ physical access cards, onboarding setup).
    "BASE": ["Facilities", "Access_Request", "Onboarding", "Offboarding"],
    # HR-GO — operational/administrative HR (payroll, formalities, compliance admin).
    "HR-GO": ["Payroll", "Compliance", "Onboarding", "Offboarding"],
    # HR-BP — people & relationships (conflicts, grievances, behaviour, wellbeing).
    "HR-BP": ["HR", "Compliance", "Onboarding", "Offboarding"],
    # Finance — money matters (reimbursements, invoices, billing).
    "Finance": ["Billing"],
}
# Note: "Other" (domain-guard catch-all) is owned by no department → admin-only.

VALID_DEPARTMENTS = set(DEPARTMENTS.keys())


def categories_for(department: str) -> list:
    """Categories owned by a department (empty if unknown)."""
    return DEPARTMENTS.get(department, [])


def departments_for_category(category: str) -> list:
    """All departments that own a category (handles shared categories)."""
    return [d for d, cats in DEPARTMENTS.items() if category in cats]


def department_for(category: str) -> str:
    """Primary (first) owning department code for grouping/display, else 'Other'."""
    ds = departments_for_category(category)
    return ds[0] if ds else "Other"


def is_valid_department(code: str) -> bool:
    return code in DEPARTMENTS
