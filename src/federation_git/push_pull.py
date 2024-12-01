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
from typing import Optional, Union, Any

import yaml
from pydantic import BaseModel, Field, field_validator
import snoop

class CurrentUser(BaseModel):
    email: str

class ProtocolFederationGitRepo(BaseModel):
    namespace: str
    name: str
    group: bool = False
    # If not specified, federate across all NS indexes
    indexes: Optional[list[str]] = None

class ProtocolFederationGit(BaseModel):
    repos: list[ProtocolFederationGitRepo]

    @field_validator("repos")
    @classmethod
    def parse_repos(cls, repos, _info):
        return list(
            [
                repo
                if isinstance(repo, ProtocolFederationGitRepo)
                else ProtocolFederationGitRepo(**repo)
                for repo in repos
            ]
        )

class ProtocolFederation(BaseModel):
    protocol: str
    data: Any

class ProtocolIndexATProto(BaseModel):
    handle: str
    uri: str
    cid: str

class ProtocolIndexGitHub(BaseModel):
    owner: str

class PolicyIndex(BaseModel):
    name: str
    protocol: str
    data: Any

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
    # TODO Load class list dynamicly
    federation: list[Any]

class Policy(BaseModel):
    data: PolicyData

class Context(BaseModel):
    current_user: CurrentUser
    policy: Policy

def federation_git(ctx: Context, active: ProtocolFederationGit):
    snoop.pp(ctx)

    # Check if current user's email is in any of the owners' emails
    owner_emails = [email for owner in ctx.policy.data.owners for email in owner.emails]
    if ctx.current_user.email not in owner_emails:
        print("Current user's email not in owners' emails.")
        # No federation preformed
        return False

    # Indirect lookup of namespace name to owner email
    current_user_namespaces = []
    for owner in ctx.policy.data.owners:
        if ctx.current_user.email in owner.emails:
            current_user_namespaces.extend(owner.namespaces)

    # TODO DEBUG REMOVE
    snoop.pp(current_user_namespaces)
    return

    for repo in active.data.repos:
        # TODO CHECK THIS LOGIC
        if not repo.group or repo.namespace not in current_user_namespaces:
            continue

        # Perform git operations: clone, pull, push
        print(f"Pushing to repo: {repo.namespace}/{repo.name}")

        # TODO DEBUG REMOVE
        continue

        repo_dir = f"{repo.namespace}_{repo.name}"
        clone_url = f"git@github.com:{repo.namespace}/{repo.name}.git"  # Adjust as needed

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
        print(f"Pushing changes to repository {repo.namespace}/{repo.name}")
        try:
            subprocess.run(["git", "-C", repo_dir, "push"], check=True)
            print(f"Successfully pushed to {repo.namespace}/{repo.name}.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to push to repository {repo.namespace}/{repo.name}: {e}")

# Helper Functions

def get_git_user_email():
    config = configparser.ConfigParser()
    config.read(str(pathlib.Path("~", ".gitconfig").expanduser()))

    try:
        return config["user"]["email"]
    except Exception as e:
        raise Exception(f"You must run: $ git config --global user.email $USER@example.com") from e

def load_protocol_cls(protocol_name):
    # TODO resourcelib + entrypoints stuff + dynamic based on known indexes
    protocols = {
        "publicdomainrelay/index-atproto-v2@v1": ProtocolIndexATProto,
        "publicdomainrelay/index-github@v1": ProtocolIndexGitHub,
        "publicdomainrelay/federation-git@v1": ProtocolFederationGit,
    }
    if protocol_name not in protocols:
        raise ValueError(f"{index_protocol!r} not found in: {protocols.keys()}")
    return protocols[protocol_name]

def build_federation_context(data):
    # Build owners
    owners_list = data.get('owners', [])
    owners = [Owner(**owner) for owner in owners_list]

    # Build namespaces
    namespaces_dict = data.get('namespaces', {})
    namespaces = {}
    for ns_name, ns_data in namespaces_dict.items():
        indexes_list = ns_data.get('indexes', [])
        indexes = []
        for index_data in indexes_list:
            protocol_name = index_data.get("protocol", "")
            protocol_cls = load_protocol_cls(protocol_name)
            protocol = protocol_cls(**index_data.get("data", {}))
            indexes.append(
                PolicyIndex(
                    **{
                        **index_data,
                        **{
                            "data": protocol,
                        },
                    },
                ),
            )
        namespaces[ns_name] = PolicyDataNamespace(indexes=indexes)

    # Build federation data
    federation_list = []
    for federation_data in data.get('federation', []):
        protocol_name = federation_data.get("protocol", "")
        protocol_cls = load_protocol_cls(protocol_name)
        protocol = protocol_cls(**federation_data.get("data", {}))
        federation_list.append(
            ProtocolFederation(
                **{
                    **federation_data,
                    **{
                        "data": protocol,
                    },
                },
            ),
        )

    policy_data = PolicyData(
        namespaces=namespaces,
        owners=owners,
        federation=federation_list
    )

    return policy_data

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

    for federation in ctx.policy.data.federation:
        if not federation.protocol.startswith(
            'publicdomainrelay/federation-git@',
        ):
            continue
        federation_git(ctx, federation)

if __name__ == "__main__":
    main()
