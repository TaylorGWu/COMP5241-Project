"""Local administrator provisioning and explicit legacy ownership assignment.

Run from backend: python -m app.auth_cli --help. Passwords are hidden prompts,
never command-line arguments. The auth schema migration backs up existing SQLite.
"""
import argparse
import getpass
import sqlite3

from app.services.auth import get_auth_store


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    create=commands.add_parser("create-admin")
    create.add_argument("--name",required=True)
    create.add_argument("--email",required=True)
    claim=commands.add_parser("claim-unowned")
    claim.add_argument("--instructor-email",required=True)
    claim.add_argument("course_ids",nargs="+")
    args=parser.parse_args(argv)
    try:
        if args.command=="create-admin":
            password=getpass.getpass("Administrator password (15–128 characters): ")
            if password!=getpass.getpass("Confirm password: "):
                parser.error("Passwords do not match")
            get_auth_store().create_user(name=args.name,email=args.email,password=password,role="admin")
            print("Administrator created.")
        else:
            assigned=get_auth_store().claim_unowned(args.instructor_email,args.course_ids)
            print("Assigned courses: "+", ".join(assigned))
    except (ValueError,sqlite3.IntegrityError) as exc:
        parser.error("The account already exists" if isinstance(exc,sqlite3.IntegrityError) else str(exc))


if __name__=="__main__":
    main()
