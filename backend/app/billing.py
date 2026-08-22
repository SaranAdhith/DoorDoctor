"""Run the billing cycle.

    python -m app.billing --generate-invoices
    python -m app.billing --generate-invoices --as-of 2026-09-01 --dry-run

Invoices every live subscription whose billing period has closed, rolling each
one forward through every period it has passed through. **Safe to run twice** —
generation is idempotent per `(subscription, period_start)`, enforced by a unique
constraint as well as by a lookup, so a cron that fires twice bills once.

In production this is a scheduled job; Phase 6 introduces APScheduler and can
call `billing_service.generate_due_invoices` directly on the same schedule.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from .config import settings
from .database import SessionLocal
from .services import billing_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DoorDoctor subscription invoices.")
    parser.add_argument(
        "--generate-invoices",
        action="store_true",
        help="Invoice every subscription whose billing period has closed.",
    )
    parser.add_argument(
        "--as-of",
        metavar="YYYY-MM-DD",
        help="Bill as though today were this date. Useful for demonstrating a renewal.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be invoiced without writing anything.",
    )
    args = parser.parse_args()

    if not args.generate_invoices:
        parser.print_help()
        return

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d") if args.as_of else None

    print(f"Database: {settings.database_url}")
    print(f"Billing as of: {(as_of or datetime.now()).strftime('%d %b %Y')}")
    if args.dry_run:
        print("Dry run — nothing will be written.")

    with SessionLocal() as db:
        invoices = billing_service.generate_due_invoices(db, as_of=as_of, dry_run=args.dry_run)

        if not invoices:
            print("\nNothing to invoice. Every subscription is billed up to date.")
            return

        verb = "would be generated" if args.dry_run else "generated"
        print(f"\n{len(invoices)} invoice(s) {verb}:\n")
        for invoice in invoices:
            print(
                f"  {invoice['number']}  {invoice['billed_to']:<28} "
                f"{invoice['period_start'].strftime('%d %b %Y')} -> "
                f"{invoice['period_end'].strftime('%d %b %Y')}  "
                f"{billing_service.format_inr(invoice['total_paise']):>12}"
            )


if __name__ == "__main__":
    main()
