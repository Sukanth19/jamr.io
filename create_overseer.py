#!/usr/bin/env python3
"""Make an existing account the Overseer (the single highest role).

    python create_overseer.py --list              # show accounts
    python create_overseer.py <username-or-name>   # make that account the overseer

Log in through the website once first so the account exists. If there is
already an overseer, they become an admin. The Overseer can't be created or
assigned through the website.
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from backend.database import get_session_local  # noqa: E402
from backend.models import User  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("account", nargs="?", help="username, display name or Spotify user ID")
    ap.add_argument("--list", action="store_true", help="list accounts and their roles")
    args = ap.parse_args()

    db = get_session_local()()
    try:
        if args.list or not args.account:
            for user in db.query(User).order_by(User.id):
                login = f"@{user.username}" if user.username else f"spotify:{user.spotify_id}"
                print(f"{user.id:>4}  {user.role:<8}  {user.display_name}  ({login})")
            if not args.account:
                return

        matches = db.query(User).filter(
            (User.spotify_id == args.account) | (User.display_name == args.account) | (User.username == args.account)
        ).all()
        if not matches:
            sys.exit(f"No account called {args.account!r}. Log in on the website first, or use --list.")
        if len(matches) > 1:
            sys.exit("Several accounts have that display name. Use the Spotify ID from --list.")
        target = matches[0]

        if target.role == "overseer":
            print(f"{target.display_name} is already the overseer.")
            return

        # Only one overseer: the current one steps down to admin
        current = db.query(User).filter(User.role == "overseer").first()
        if current:
            current.role = "admin"
            db.flush()
            print(f"{current.display_name} is now an admin.")

        target.role = "overseer"
        db.commit()
        print(f"{target.display_name} is now the overseer.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
