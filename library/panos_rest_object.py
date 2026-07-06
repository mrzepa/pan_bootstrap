#!/usr/bin/python

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET

import requests
import urllib3
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r"""
---
module: panos_rest_object
short_description: Manage PAN-OS REST API objects
description:
  - Creates or updates PAN-OS objects exposed only through the REST API.
  - Intended for focused local project gaps such as PAN-OS SD-WAN objects.
options:
  ip_address:
    type: str
    required: true
  username:
    type: str
  password:
    type: str
  api_key:
    type: str
  endpoint:
    description:
      - REST API endpoint after the version path, such as C(Network/SDWANInterfaceProfiles).
    type: str
    required: true
  name:
    type: str
    required: true
  spec:
    description:
      - REST object entry spec. C(@name), C(@location), and C(@vsys) are added automatically when omitted.
    type: dict
    required: true
  create_with_name:
    description:
      - Include C(name) as a query parameter on create requests.
      - Some PAN-OS REST endpoints, including C(Policies/SecurityRules), require this.
    type: bool
    default: false
  api_version:
    type: str
    default: v11.2
  location:
    type: str
    default: vsys
  vsys:
    type: str
    default: vsys1
  state:
    type: str
    choices:
      - present
      - absent
    default: present
  validate_certs:
    type: bool
    default: false
  timeout:
    type: int
    default: 30
"""

EXAMPLES = r"""
- name: Create SD-WAN interface profile
  panos_rest_object:
    ip_address: 192.0.2.10
    username: admin
    password: "{{ firewall_password }}"
    endpoint: Network/SDWANInterfaceProfiles
    name: ISP1
    spec:
      link-tag: ISP1
      link-type: Ethernet
      path-monitoring: Aggressive
"""


IGNORED_COMPARE_KEYS = {"@location", "@vsys", "@uuid", "@oldname"}


class PanosRestError(Exception):
    pass


def normalized(value):
    if isinstance(value, dict):
        return {
            key: normalized(val)
            for key, val in value.items()
            if key not in IGNORED_COMPARE_KEYS
        }
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


class PanosRestApi:
    def __init__(self, module):
        self.module = module
        self.host = module.params["ip_address"].replace("https://", "").replace("http://", "").strip("/")
        self.verify = module.params["validate_certs"]
        self.timeout = module.params["timeout"]
        self.api_key = module.params["api_key"]
        self.session = requests.Session()
        self.session.verify = self.verify
        if not self.verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def xml_base_url(self):
        return f"https://{self.host}/api/"

    def keygen(self):
        username = self.module.params["username"]
        password = self.module.params["password"]
        if not username or not password:
            self.module.fail_json(msg="username and password are required when api_key is not supplied")
        response = self.session.get(
            self.xml_base_url,
            params={"type": "keygen", "user": username, "password": password},
            timeout=self.timeout,
        )
        root = ET.fromstring(response.text)
        if root.attrib.get("status") != "success":
            self.module.fail_json(msg=f"PAN-OS keygen failed: {response.text}")
        key = root.findtext("./result/key")
        if not key:
            self.module.fail_json(msg="PAN-OS keygen response did not include an API key")
        self.api_key = key
        return key

    def rest_url(self):
        endpoint = self.module.params["endpoint"].strip("/")
        version = self.module.params["api_version"].strip("/")
        return f"https://{self.host}/restapi/{version}/{endpoint}"

    def headers(self):
        if not self.api_key:
            self.keygen()
        return {"X-PAN-KEY": self.api_key, "Content-Type": "application/json"}

    def params(self, include_name=True):
        params = {
            "location": self.module.params["location"],
            "vsys": self.module.params["vsys"],
        }
        if include_name:
            params["name"] = self.module.params["name"]
        return params

    def request(self, method, *, include_name=True, payload=None):
        response = self.session.request(
            method,
            self.rest_url(),
            headers=self.headers(),
            params=self.params(include_name=include_name),
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return None
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise PanosRestError(f"REST API returned non-JSON response: {response.text}") from exc
        if response.status_code >= 400 or body.get("@status") == "error":
            raise PanosRestError(body.get("message") or response.text)
        return body

    def get(self):
        body = self.request("GET")
        if body is None:
            return None
        entries = body.get("result", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        return entries[0] if entries else None

    def create(self, spec):
        return self.request(
            "POST",
            include_name=self.module.params["create_with_name"],
            payload={"entry": spec},
        )

    def update(self, spec):
        return self.request("PUT", payload={"entry": spec})

    def delete(self):
        return self.request("DELETE")


def build_spec(module):
    spec = copy.deepcopy(module.params["spec"])
    spec.setdefault("@name", module.params["name"])
    spec.setdefault("@location", module.params["location"])
    if module.params["location"] == "vsys":
        spec.setdefault("@vsys", module.params["vsys"])
    return spec


def run_module():
    module = AnsibleModule(
        argument_spec={
            "ip_address": {"type": "str", "required": True},
            "username": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "api_key": {"type": "str", "no_log": True},
            "endpoint": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "spec": {"type": "dict", "required": True},
            "create_with_name": {"type": "bool", "default": False},
            "api_version": {"type": "str", "default": "v11.2"},
            "location": {"type": "str", "default": "vsys"},
            "vsys": {"type": "str", "default": "vsys1"},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "validate_certs": {"type": "bool", "default": False},
            "timeout": {"type": "int", "default": 30},
        },
        required_one_of=[["api_key", "username"]],
        required_together=[["username", "password"]],
        supports_check_mode=True,
    )

    api = PanosRestApi(module)
    desired = build_spec(module)
    try:
        current = api.get()
        if module.params["state"] == "absent":
            changed = current is not None
            if changed and not module.check_mode:
                api.delete()
            module.exit_json(changed=changed, current=current)

        changed = current is None or normalized(current) != normalized(desired)
        if changed and not module.check_mode:
            if current is None:
                api.create(desired)
            else:
                api.update(desired)
        module.exit_json(changed=changed, current=current, desired=desired)
    except PanosRestError as exc:
        module.fail_json(msg=str(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
