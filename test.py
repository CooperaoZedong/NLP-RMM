from synth.utils.json_utils import extract_json_block

txt = """Some chatter
<json>{"workflowSteps":[{"workflowStepType":1,"triggerType":2,"triggerSubType":"Manual","skipOffline":true,"displayName":"Ad-hoc"}]}</json>
More chatter"""
obj = extract_json_block(txt)
assert "workflowSteps" in obj
print("ok")
