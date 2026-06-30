#!/usr/bin/python

import os
from ansible.module_utils.basic import AnsibleModule
from pypanrestv2.Base import Panorama
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_module():
    module_args = {
        "pano_ip": {"type": "str", "required": True},
        "pano_api_key": {"type": "str", "required": True, "no_log": True},
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    pano_ip = module.params["pano_ip"]
    pano_api_key = module.params["pano_api_key"]

    try:
        # Initialize Panorama connection
        pano = Panorama(pano_ip, api_key=pano_api_key)
        
        # Get the auth key
        auth_key = pano.get_panorama_authkey()
        
        if auth_key:
            if not module.check_mode:
                os.environ['PANORAMA_AUTH_KEY'] = auth_key
            module.exit_json(
                changed=False,
                msg=(
                    "Successfully retrieved Panorama auth key"
                    if not module.check_mode
                    else "Successfully retrieved Panorama auth key in check mode"
                ),
                auth_key=auth_key
            )
        else:
            module.fail_json(msg="Failed to get Panorama auth key")

    except Exception as e:
        module.fail_json(msg=f"Error getting Panorama auth key: {str(e)}")

if __name__ == '__main__':
    run_module()
