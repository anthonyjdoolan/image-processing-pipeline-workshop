"""Workshop configuration - loaded from cdk.json. Edit values there."""
import json
import os

with open(os.path.join(os.path.dirname(__file__), "..", "cdk.json")) as _f:
    _CTX = json.load(_f)["context"]

REGION = _CTX["region"]
BUCKET_NAME = _CTX["bucket_name"]
ENDPOINT_NAME = _CTX["endpoint_name"]
STACK_NAME = _CTX["stack_name"]
RESOURCE_PREFIX = _CTX["resource_prefix"]
TAGS = [{"Key": k, "Value": v} for k, v in _CTX.get("tags", {}).items()]
