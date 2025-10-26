from typing import Dict, Any, List, Set
from datetime import datetime, timezone
import re

from synth.utils.contracts import NOTIFICATION_TYPES, SCOPE_MAP, ALLOWED_ACTION_TYPES

DATE_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

def _is_trigger(step: Dict[str, Any]) -> bool:
    return step.get("workflowStepType") == 1

def _is_action(step: Dict[str, Any]) -> bool:
    return step.get("workflowStepType") == 0

def _is_condition(step: Dict[str, Any]) -> bool:
    return step.get("workflowStepType") == 2

def _walk_sequences(seq: List[Dict[str, Any]]):
    for s in seq:
        yield s
        if _is_condition(s):
            for x in _walk_sequences(s.get("positiveOutcome", []) or []):
                yield x
            for x in _walk_sequences(s.get("negativeOutcome", []) or []):
                yield x

def _normalize_schedule_dates(step: Dict[str, Any]):
    sched = step.get("schedule")
    if not sched:
        return
    # enforce UTC now if not matching iso
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
    sd = sched.get("startDate")
    if not isinstance(sd, str) or not DATE_ISO_RE.match(sd):
        sched["startDate"] = now
    if not sched.get("timezone"):
        sched["timezone"] = "UTC"

def _validate_trigger_first_only(wf: Dict[str, Any]):
    steps = wf.get("workflowSteps", [])
    assert steps and _is_trigger(steps[0]), "First step must be a TRIGGER"
    for i, s in enumerate(steps):
        if _is_trigger(s) and i != 0:
            raise AssertionError("Trigger may appear only once and only as the first step")
    # triggers are not allowed inside condition branches (enforce strictly)
    for s in steps[1:]:
        if _is_condition(s):
            for x in _walk_sequences([s]):
                if _is_trigger(x):
                    raise AssertionError("Trigger cannot appear inside condition branches")

def _validate_trigger(t: Dict[str, Any]):
    ttype = t.get("triggerType")
    sub  = t.get("triggerSubType")
    if ttype == 0:  # Notification
        nt = t.get("notificationType")
        assert isinstance(nt, str), "notificationType required for notification trigger"
        assert nt in NOTIFICATION_TYPES, f"notificationType {nt} not allowed"
        assert sub == nt, "triggerSubType must equal notificationType"
    elif ttype == 1:  # External
        assert "notificationType" not in t or t["notificationType"] in (None, ""), "External trigger must NOT specify notificationType"
        assert isinstance(sub, str) and sub, "External trigger must have non-empty triggerSubType"
    elif ttype == 2:
        assert isinstance(sub, str), "triggerSubType required for triggerType=2"
        if sub == "Manual":
            assert "notificationType" not in t or t["notificationType"] in (None, ""), "Manual trigger must NOT specify notificationType"
        elif sub == "Scheduled":
            sched = t.get("schedule") or {}
            fi = ((sched.get("frequencyInterval") or {}), sched.get("frequencySubinterval"))
            uuid = fi[0].get("uuid"); fid = fi[0].get("id"); text = fi[0].get("text")
            if fid == 1:
                assert uuid == 1 and text == "Daily" and fi[1] == 0, "Daily schedule requires uuid=1,id=1,text=Daily,subinterval=0"
            elif fid == 2:
                assert uuid == 4 and text == "Weekly", "Weekly schedule requires uuid=4,id=2,text=Weekly"
                subint = fi[1]; assert isinstance(subint, int) and 1 <= subint <= 127, "Weekly frequencySubinterval must be 1..127 (bitmask of days)"
            elif fid == 3:
                assert uuid == 5 and text == "Monthly", "Monthly schedule requires uuid=5,id=3,text=Monthly"
                assert sched.get("frequencySubinterval") in (0,128,256), "Monthly frequencySubinterval must be 0, 128 or 256"
            else:
                raise AssertionError("Unknown schedule frequencyInterval.id")
            _normalize_schedule_dates(sched)
        else:
            raise AssertionError("Unknown triggerSubType for triggerType=2")
    else:
        raise AssertionError("Unknown triggerType")

def _validate_end_is_last(seq: List[Dict[str, Any]]):
    seen_end = False
    for idx, s in enumerate(seq):
        if _is_condition(s):
            _validate_end_is_last(s.get("positiveOutcome", []) or [])
            _validate_end_is_last(s.get("negativeOutcome", []) or [])
            if seen_end:
                raise AssertionError("No steps allowed after End Workflow in a branch")
        elif _is_action(s) and s.get("actionType") == 15:
            # must be literally the last in this seq
            if idx != len(seq) - 1:
                raise AssertionError("End Workflow must be the last step in its branch")
            seen_end = True
        elif seen_end:
            raise AssertionError("No steps allowed after End Workflow in a branch")

def _collect_produced_variables(seq: List[Dict[str, Any]]):
    """
    Returns dict name->type_code (0=Boolean,1=Number,2=Text,3=DateTime)
    """
    vars_map = {}
    for s in _walk_sequences(seq):
        if _is_action(s):
            at = s.get("actionType")
            p  = s.get("parameters") or {}
            if at in (24,27,36):
                if p.get("captureOutput") and p.get("outputVariable"):
                    vars_map[p["outputVariable"]] = 2  # Text
            elif at == 37:
                vname = p.get("variableName")
                vtype = p.get("variableType")
                if isinstance(vname, str) and vname:
                    # map to 0..3 (Boolean,Number,Text,DateTime)
                    typemap = {
                        0:0,1:0,2:0,3:0,4:0,5:0,7:0,9:0,16:0,  # Booleans
                        11:1,                                   # Number
                        6:2,10:2,12:2,13:2,14:2,15:2,           # Text/various
                        8:3                                     # DateTime
                    }
                    vars_map[vname] = typemap.get(vtype, 2)
    return vars_map

def _scan_string_placeholders(val) -> List[str]:
    out=[]
    if isinstance(val, str):
        out += re.findall(r"#([0-9]{6,})", val)
    elif isinstance(val, list):
        for x in val: out += _scan_string_placeholders(x)
    elif isinstance(val, dict):
        for x in val.values(): out += _scan_string_placeholders(x)
    return out

def _validate_variables_links(seq: List[Dict[str, Any]]):
    produced = _collect_produced_variables(seq)
    produced_names = set(produced.keys())

    # uniqueness of variable names
    if len(produced_names) != len(produced):
        raise AssertionError("Variable names must be unique within workflow")

    for s in _walk_sequences(seq):
        if _is_condition(s):
            for r in (s.get("rules") or []):
                if r.get("propertyId") == "Variable":
                    vname = r.get("variablesId")
                    assert vname in produced_names, f"Rule references unknown variable '{vname}'"
        if _is_action(s):
            p = s.get("parameters") or {}
            # placeholders in strings must have a matching entry in parameters.variables
            placeholders = set(_scan_string_placeholders(p))
            vars_arr = p.get("variables") or []
            ids_in_vars = { v.get("variableId") for v in vars_arr if isinstance(v, dict) }
            if placeholders and not placeholders.issubset(ids_in_vars):
                missing = placeholders - ids_in_vars
                raise AssertionError(f"Missing variable references for ids: {sorted(missing)}")
            # each VarRef.sourceId must correspond to a produced variable name
            for v in vars_arr:
                src = v.get("sourceId"); tp = v.get("type")
                assert src in produced_names, f"VarRef.sourceId '{src}' not produced earlier"
                # optional: type compatibility can be checked here using produced[src] vs tp

def _validate_actions(seq: List[Dict[str, Any]]):
    for s in _walk_sequences(seq):
        if _is_action(s):
            at = s.get("actionType")
            assert at in ALLOWED_ACTION_TYPES, f"Unknown actionType {at}"
            p = s.get("parameters")
            if at == 26 and isinstance(p, dict):
                if p.get("type") == 1:
                    assert 0 < int(p.get("minutes", -1)) < 60, "Reboot 'minutes' must be 1..59 when type==1"

def _validate_rules_operators(seq: List[Dict[str, Any]]):
    for s in _walk_sequences(seq):
        if _is_condition(s):
            for r in (s.get("rules") or []):
                pid = r.get("propertyId")
                op = r.get("operator")
                assert isinstance(op, int) and 0 <= op <= 12, "operator must be 0..12"
                if pid == "oSType":
                    assert r.get("value") in (1,2,3), "oSType value must be 1,2,3"
                if pid == "scope":
                    name = r.get("scopeName"); sid = r.get("scopeId")
                    assert name in SCOPE_MAP, f"Unknown scopeName '{name}'"
                    if sid is not None:
                        assert sid == SCOPE_MAP[name], f"scopeId {sid} does not match scopeName '{name}'"

def semantic_validate_workflow(wf: Dict[str, Any]):
    steps = wf.get("workflowSteps", [])
    _validate_trigger_first_only(wf)
    # trigger details
    _validate_trigger(steps[0])
    # End Workflow position
    _validate_end_is_last(steps)
    # Actions & rules
    _validate_actions(steps)
    _validate_rules_operators(steps)
    # Variables linkages
    _validate_variables_links(steps)

