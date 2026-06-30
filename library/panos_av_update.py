#!/usr/bin/python

import logging
from ansible.module_utils.basic import AnsibleModule
from pypanrestv2.Base import Firewall
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

def run_module():
    # Define the module's arguments
    module_args = {
        "ip_address": {"type": "str", "required": True},
        "username": {"type": "str", "required": True},
        "password": {"type": "str", "required": True, "no_log": True},
    }

    # Create an AnsibleModule object
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Extract parameters
    ip = module.params["ip_address"]
    user = module.params["username"]
    password = module.params["password"]

    # Execute the function
    try:
        if module.check_mode:
            module.exit_json(changed=True, msg="Check mode: would update anti-virus definitions.")

        fw = Firewall(ip, username=user, password=password)
        fw.update_av()

        # Return success
        module.exit_json(changed=True, msg="Successfully updated anti-virus.")

    except Exception as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    run_module()
