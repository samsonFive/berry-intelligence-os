"""Compatibility for provisioning used by the first live account release."""
from app.runtime_config import resolve_inbox_dir
from app.services import analyst_accounts


def accounts_path():
    return analyst_accounts.account_path(resolve_inbox_dir())


def add_user(username, password):
    analyst_accounts.create_account(resolve_inbox_dir(), username, password)


def additional_credentials_match(username, password):
    return analyst_accounts.account_credentials_match(resolve_inbox_dir(), username, password)


def first_login_destination(username, destination):
    return analyst_accounts.first_login_destination(resolve_inbox_dir(), username, destination)
