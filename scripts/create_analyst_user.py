"""Create an analyst account without logging or storing its plaintext password."""
import argparse
import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.runtime_config import resolve_inbox_dir
from app.services.analyst_accounts import create_account

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Password: ")
    create_account(resolve_inbox_dir(), args.username, password)
    print("Account created. First login opens Help. Analyst workspace data is shared.")
