import os
import sys
import json
import atexit
import base64
import shutil
import pprint
import zipfile
import hashlib
import pathlib
import asyncio
import argparse
import warnings
import subprocess
import configparser
from typing import Optional

import yaml
from pydantic import BaseModel, Field

class CurrentUser(BaseModel):
    email: str

class FederationGitRepo(BaseModel):
    namespace: str
    repo: str
    group: bool = False
    # If not specified, federate across all NS indexes
    indexes: Optional[list[str]] = None

class FederationGitContext(BaseModel):
    repos: list[FederationGitRepo]

class PolicyIndex(BaseModel):
    name: str
    protocol: str
    data: dict

class PolicyDataNamespace(BaseModel):
    indexes: list[PolicyIndex]

class Owner(BaseModel):
    actors: list[str]
    emails: list[str]
    namespaces: list[str]
    keys: list[str]

class PolicyData(BaseModel):
    namespaces: dict[str, PolicyDataNamespace]
    owners: list[Owner]
    # List of federation entries from YAML
    federation: list[dict]

class Policy(BaseModel):
    data: PolicyData

class Context(BaseModel):
    current_user: CurrentUser
    policy: Policy

def federation_git(ctx: Context, active: FederationGitContext):
    # Check if current user's email is in any of the owners' emails
    owner_emails = [email for owner in ctx.policy.data.owners for email in owner.emails]
    if ctx.current_user.email not in owner_emails:
        print("Current user's email not in owners' emails.")
        return

    # Indirect lookup of namespace name to owner email
    current_user_namespaces = []
    for owner in ctx.policy.data.owners:
        if ctx.current_user.email in owner.emails:
            current_user_namespaces.extend(owner.namespaces)

    for repo in active.repos:
        if not repo.group or repo.namespace not in current_user_namespaces:
            continue

        # Perform git operations: clone, pull, push
        print(f"Pushing to group repo: {repo.namespace}/{repo.repo}")
        repo_dir = f"{repo.namespace}_{repo.repo}"
        clone_url = f"git@github.com:{repo.namespace}/{repo.repo}.git"  # Adjust as needed

        # Clone the repository if it doesn't exist
        if not os.path.isdir(repo_dir):
            print(f"Cloning repository {clone_url} into {repo_dir}")
            try:
                subprocess.run(["git", "clone", clone_url, repo_dir], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone repository {clone_url}: {e}")
                continue
        else:
            # Pull the latest changes
            print(f"Repository {repo_dir} exists. Pulling latest changes.")
            try:
                subprocess.run(["git", "-C", repo_dir, "pull"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to pull repository {repo_dir}: {e}")
                continue

        # Push changes to the repository
        print(f"Pushing changes to repository {repo.namespace}/{repo.repo}")
        try:
            subprocess.run(["git", "-C", repo_dir, "push"], check=True)
            print(f"Successfully pushed to {repo.namespace}/{repo.repo}.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to push to repository {repo.namespace}/{repo.repo}: {e}")

# Helper Functions

def get_git_user_email():
    config = configparser.ConfigParser()
    config.read(str(pathlib.Path("~", ".gitconfig").expanduser()))

    try:
        return config["user"]["email"]
    except Exception as e:
        raise Exception(f"You must run: $ git config --global user.email $USER@example.com") from e

def build_federation_context(data):
    # Build owners
    owners_list = data.get('owners', [])
    owners = [Owner(**owner) for owner in owners_list]

    # Build namespaces
    namespaces_dict = data.get('namespaces', {})
    namespaces = {}
    for ns_name, ns_data in namespaces_dict.items():
        indexes_list = ns_data.get('indexes', [])
        indexes = [PolicyIndex(**index) for index in indexes_list]
        namespaces[ns_name] = PolicyDataNamespace(indexes=indexes)

    # Build federation data
    federation_list = data.get('federation', [])

    policy_data = PolicyData(
        namespaces=namespaces,
        owners=owners,
        federation=federation_list
    )

    return policy_data

def get_active_repos(policy):
    active_repos = []
    for federation in policy.data.federation:
        if federation.get('protocol') == 'publicdomainrelay/federation-git@v1':
            repos = federation.get('data', {}).get('repos', [])
            active_repos.extend([FederationGitRepo(**repo) for repo in repos])
    return active_repos

# Main Execution Function

def main():
    # Load the YAML configuration
    # YAML_INPUT = "policy.yaml"
    policy_obj = yaml.safe_load(sys.stdin.read())
    # data = yaml_data.get('data', {})

    # Build the federation context
    policy_data = build_federation_context(policy_obj["data"])

    # Get current user's email
    git_email = get_git_user_email()
    current_user = CurrentUser(email=git_email)

    ctx = Context(
        current_user=current_user,
        policy=Policy(
            data=policy_data,
        ),
    )

    # Get active repositories
    active_repos = get_active_repos(ctx.policy)
    active = FederationGitContext(repos=active_repos)

    import snoop
    snoop.pp(ctx)

    # Perform federation git operations
    # federation_git(ctx, active)

if __name__ == "__main__":
    main()
