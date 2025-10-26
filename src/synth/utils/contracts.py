import json, pathlib
from typing import Dict, Any, Set

NOTIFICATION_TYPES = {
    "SERVICE_STOP","SERVICE_MISSED","USER_LOGGED_IN","USER_LOGGED_OUT",
    "LOW_MEMORY","HIGH_CPU_USAGE","HIGH_PING_TIME","PING_ERROR",
    "LOW_HDD_FREE_SPACE","COMPUTER_OFFLINE","COMPUTER_BACK_ONLINE",
    "PORT_NOT_AVAILABLE","EVENT_LOG_WATCH","REBOOT_REQUIRED",
    "LOW_BATTERY","WINDOWS_UPDATES_AVAILABLE","PROCESS_STARTED",
    "PROCESS_STOPPED","PERFORMANCE_COUNTER","APPLICATIONS_ADDED",
    "USB_DEVICE_INSERT","USB_DEVICE_REMOVE","IP_CHANGED","USER_SUPPORT_REQUEST",
    "WEB_SITE_ERROR","SNMP_ALERT","SECURITY_FIREWALL_DISABLED",
    "SECURITY_ANTIVIRUS_DISABLED","HDD_SMART_FAILURE",
    "ANTIVIRUS_DEFINITIONS_OUTDATED","COMPUTER_REGISTERED"
}

ALLOWED_ACTION_TYPES = {
    1,2,9,14,15,19,20,21,22,23,24,25,26,27,31,32,33,34,35,36,37,38
}

# Predefined scopes and ids
SCOPE_MAP = {
    "All Windows Computers": -13,
    "All Windows Servers": -12,
    "All Windows Server 2012": -8,
    "All Windows Server 2016": -9,
    "All Windows Server 2019": -10,
    "All Windows Server 2022": -11,
    "All Windows Server 2025": -16,
    "All Windows 10 Computers": -14,
    "All Windows 11 Computers": -15
}


def load_schema(path: str) -> Dict[str, Any]:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

def load_catalog(path: str) -> Set[str]:
    return set(ALLOWED_ACTION_TYPES)

def schema_summary(schema: dict) -> str:
    return "Root key: workflowSteps (array). Steps: Trigger(ActionType=1..), Action(workflowStepType=0), Condition(workflowStepType=2)."
