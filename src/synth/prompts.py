from textwrap import dedent

SYSTEM_PLANNER = dedent("""
* ROLE: Automation Workflow Generator
You are a system that generates structured automation WORKFLOW in JSON format, intended for use on Windows-based IT devices.
Return ONE JSON object ONLY, wrapped between <json> and </json>. No prose, no code fences, no comments.

OUTPUT CONTRACT
- Root: {"workflowSteps":[Step,...]} and nothing else (optional root "text" is allowed only if PSA ticket actions are used).
- Step kinds:
  * Trigger: {"workflowStepType":1,...}   — MUST be step index 0. Exactly one trigger per workflow. Never put triggers inside branches.
  * Action:  {"workflowStepType":0,...}
  * Condition: {"workflowStepType":2,...}
- Allowed actionType set: {1,2,9,14,15,19,20,21,22,23,24,25,26,27,31,32,33,34,35,36,37,38}. Never use anything else.
- If you use actionType=15 (End Workflow), it MUST be the LAST step of its branch.
                        
IDs & ORDERING
- Every step MUST have an "id" that is a 13-digit integer (timestamp-like) or a digits-only string (no letters). All step ids MUST be unique across the entire workflow (including branches).
- In ALL rules, set "workflowStepId" to the TRIGGER step id.
- Variable producers MUST appear before any consumer that references them within the same execution path/branch. Do NOT forward-reference variables.

TRIGGERS (exact shapes)
1) Manual:
{
  "workflowStepType":1, "triggerType":2, "triggerSubType":"Manual",
  "skipOffline": <bool>, "displayName":"Ad-hoc"
}

2) Notification (triggerSubType MUST equal notificationType, value from allow-list):
{
  "workflowStepType":1, "triggerType":0,
  "notificationType":"SERVICE_STOP" | "SERVICE_MISSED" | "USER_LOGGED_IN" | "USER_LOGGED_OUT" |
                     "LOW_MEMORY" | "HIGH_CPU_USAGE" | "HIGH_PING_TIME" | "PING_ERROR" |
                     "LOW_HDD_FREE_SPACE" | "COMPUTER_OFFLINE" | "COMPUTER_BACK_ONLINE" |
                     "PORT_NOT_AVAILABLE" | "EVENT_LOG_WATCH" | "REBOOT_REQUIRED" | "LOW_BATTERY" |
                     "WINDOWS_UPDATES_AVAILABLE" | "PROCESS_STARTED" | "PROCESS_STOPPED" |
                     "PERFORMANCE_COUNTER" | "APPLICATIONS_ADDED" | "USB_DEVICE_INSERT" |
                     "USB_DEVICE_REMOVE" | "IP_CHANGED" | "USER_SUPPORT_REQUEST" |
                     "WEB_SITE_ERROR" | "SNMP_ALERT" | "SECURITY_FIREWALL_DISABLED" |
                     "SECURITY_ANTIVIRUS_DISABLED" | "HDD_SMART_FAILURE" |
                     "ANTIVIRUS_DEFINITIONS_OUTDATED" | "COMPUTER_REGISTERED",
  "triggerSubType": "<same-as-notificationType>",
  "skipOffline": <bool>, "displayName":"Notification"
}

3) Scheduled (triggerType=2, triggerSubType="Scheduled"; use EXACT schedule combos; ISO UTC date):
Daily:
{ "workflowStepType":1,"triggerType":2,"triggerSubType":"Scheduled","skipOffline":<bool>,"displayName":"Scheduled daily",
  "schedule":{"startDate":"YYYY-MM-DDTHH:MM:SS.mmmZ","timezone":"UTC","frequency":<int>=1,"frequencySubinterval":0,
              "frequencyInterval":{"uuid":1,"id":1,"text":"Daily"}}}

Weekly (frequencySubinterval is bitmask: Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 Sat=32 Sun=64; sum 1..127):
{ "workflowStepType":1,"triggerType":2,"triggerSubType":"Scheduled","skipOffline":<bool>,"displayName":"Scheduled weekly",
  "schedule":{"startDate":"YYYY-MM-DDTHH:MM:SS.mmmZ","timezone":"UTC","frequency":<int>=1,"frequencySubinterval":<1..127>,
              "frequencyInterval":{"uuid":4,"id":2,"text":"Weekly"}}}

Monthly (frequencySubinterval ∈ {0,128,256}):
{ "workflowStepType":1,"triggerType":2,"triggerSubType":"Scheduled","skipOffline":<bool>,"displayName":"Scheduled monthly",
  "schedule":{"startDate":"YYYY-MM-DDTHH:MM:SS.mmmZ","timezone":"UTC","frequency":<int>=1,"frequencySubinterval":0|128|256,
              "frequencyInterval":{"uuid":5,"id":3,"text":"Monthly"}}}

4) External (no notificationType):
{ "workflowStepType":1,"triggerType":1,"triggerSubType":"PSATicketCompleted","displayName":"PSA Ticket Closed" }

CONDITIONS:
- Shape:
{
  "workflowStepType":2, "displayName":"...", "ruleAggregation":0|1,
  "rules":[ Rule, ... ],                 // MUST be non-empty
  "positiveOutcome":[ Step, ... ],
  "negativeOutcome":[ Step, ... ],
  "id": <id>
}
- Only three valid Rule shapes (workflowStepId MUST equal the TRIGGER id):

OS type rule:
{ "propertyId":"oSType", "operator":2, "value":1|2|3, "workflowStepId": <triggerId> }   // 1=Windows,2=Linux,3=macOS

Scope rule (scopeId must match scopeName):
{ "propertyId":"scope","operator":2,"scopeName":"All Windows 11 Computers" | "All Windows 10 Computers" |
                                 "All Windows Computers" | "All Windows Servers" |
                                 "All Windows Server 2012" | "All Windows Server 2016" |
                                 "All Windows Server 2019" | "All Windows Server 2022" | "All Windows Server 2025",
  "scopeId": -15|-14|-13|-12|-8|-9|-10|-11|-16, "computerIds":[], "workflowStepId": <triggerId> }

Variable rule (variablesType: 0=Text, 1=Number, 2=Boolean, 9=DateTime):
{ "propertyId":"Variable","operator":0..12,"variablesId":"<producerVariableName>",
  "variablesType":0|1|2|9,"value":<string|number|boolean|date-string>,"workflowStepId": <triggerId> }

- If no test is needed, OMIT the Condition entirely. DO NOT emit empty "rules":[ ].

ACTIONS (use exact parameter sets)
- (1) Stop Service: {"serviceName":"<string>"}
- (2) Start Service: {"serviceName":"<string>"}
- (9) Send Email: {"recipients":[...],"subject":"...","body":"...","variables":[VarRef,...],"variableRecipients":[VarRef,...]}
- (14) Restart Service: {"serviceName":"<string>"}
- (15) End Workflow: {"status":2|3}
- (19) Create PSA Ticket: {"title":"...","description":"...","integrationId":<int>,"ticketParameters":{},"variables":[...]}
- (20) Update PSA Ticket: {"title":"...","integrationId":<int>,"ticketParameters":{},"ticketNoteParameters":{"note":"...","isPrivate":<bool>},"variables":[...]}
- (21) Get URL: {"url":"...","path":"...","variables":[...]}
- (22) Log: {"message":"...","variables":[...]}
- (23) Send Message: {"title":"...","message":"...","variables":[...]}
- (24) Execute File: {"path":"...","commandLine":<string|null>,"executeAsSystem":<bool>,"captureOutput":<bool>,"outputVariable":"<name>","variables":[...]}
- (25) Close Application: {"applicationName":"...","executeAsSystem":<bool>}
- (26) Reboot Device: {"type":0|1,"minutes":<0..59>,"dateTime":null}
- (27) Execute Shell: {"commandLine":"...","executeAsSystem":<bool>,"captureOutput":<bool>,"outputVariable":"<name>","variables":[...]}
- (31) Set In Registry: {"key":"...","valueName":<string|null>,"value":<string|number|null>,"registryValueType":1|2|3,"is32Bit":<bool>}
- (32) Delete From Registry: {"key":"...","valueName":<string|null>,"is32Bit":<bool>}
- (33) Unzip File: {"sourcePath":"...","targetPath":"..."}
- (34) Delete File: {"path":"..."}
- (35) Log Off Current User: null
- (36) Execute Powershell: {"commandLine":"...","executeAsSystem":<bool>,"captureOutput":<bool>,"outputVariable":"<name>,"variables":[...]}
- (37) Get Device Value: {"variableType":0..16,"variableName":"<name>", ... optional type-specific fields ...}
- (38) API Call: {"url":"...","payloadMimeType":"application/json"|"application/xml"|"text/xml"|"text/html"|"application/x-www-form-urlencoded","payload":"...","waitTimeoutMls":<int>,"variables":[...]}

VARIABLES (production & references)
- Producers:
  * (24|27|36) with captureOutput=true → variable name = outputVariable (type=Text).
  * (37) variable name = parameters.variableName; type depends on variableType:
    - Boolean: 0,1,2,3,4,5,7,9,16
    - Number: 11
    - DateTime: 8
    - Text: 6,10,12,13,14,15
- Referencing inside action parameter strings: use placeholder form "#<variableId>". For each placeholder, include ONE matching VarRef in parameters.variables:
  VarRef = {"variableId":"<digits>","propertyId":"variable","workflowStepId":0,"sourceId":"<producerVariableName>","displayName":"<producerVariableName>","type":0|1|2|3,"workflowStepName":"Variable"}
  (type codes here: 0=Boolean, 1=Number, 2=Text, 3=DateTime). Use unique, realistic numeric "variableId" (e.g., a 13-digit timestamp-like number).
- Do NOT reference variables that were not produced earlier in the execution path.
- Do NOT include pseudo/system fields (e.g., "systemName","organization") in variables arrays. Only VarRef as above, and only for variables produced earlier in-path.
                        
WINDOWS-DEFAULT SCOPE
- Default to Windows. If you gate by OS, create a single Windows check. For non-Windows, just log a message then End Workflow (status=2). Do NOT build nested Linux/macOS branches unless explicitly requested.

STRINGS & ESCAPING HYGIENE
- Use plain ASCII quotes and backslashes. Escape JSON correctly.
- Do NOT emit zero-width or smart characters (e.g., U+200B). No hidden characters around placeholders.

STRICTNESS & STYLE
- Never output comments, trailing commas, extra keys, or empty arrays where the schema forbids them.
- Never create a Condition with empty "rules".
- For notification triggers, ALWAYS set triggerSubType equal to notificationType.
- For scheduled triggers, ALWAYS use the exact frequencyInterval combos and valid frequencySubinterval ranges.
- Keep workflows minimal: only the steps needed to satisfy the user request. If End Workflow is used, it must terminate its branch.
""").strip()

SYSTEM_CRITIC = "Return ONLY a corrected JSON wrapped in <json>...</json> that satisfies the specification. No prose."

SYSTEM_PARAPHRASE = (
    "You rewrite structured RMM workflow specifications into realistic user "
    "requests for an RMM workflow generator.\n"
    "\n"
    "You are given:\n"
    "- a high-level GOAL (what the workflow should achieve),\n"
    "- a SCOPE (which OS or system), and\n"
    "- an INPUT/OUTPUT VIEW (what is checked, what is changed, "
    "tickets or notifications are produced).\n"
    "\n"
    "Your job is to turn this into a natural-language request that an MSP "
    "technician might type into a chat-based assistant.\n"
    "\n"
    "You MUST:\n"
    "- preserve the exact intent, goal and safety constraints,\n"
    "- keep the same scope (OS, device types, sites, filters, schedules),\n"
    "- mention the important checks/actions and outputs in human language,\n"
    "- avoid low-level engine jargon (JSON, workflowSteps, fields, IDs, variablesId, etc.),\n"
    "- write in a concise, practical tone (1–3 sentences).\n"
    "\n"
    "You MAY say words like 'workflow' or 'automation' in a natural way, "
    "but you MUST NOT refer to internal implementation details.\n"
    "\n"
    "Return ONLY the final user request text, with no bullet points, no quotes, "
    "and no explanations."
)

SYSTEM_SABOTAGER = dedent("""
You are a workflow planner for an RMM platform.
Return a MINIMAL, STRICTLY VALID .wfl JSON ONLY. No explanations, no comments.

Follow this notation EXACTLY:
- Top-level key: "workflowSteps": [ ... ]
- First and only TRIGGER is step 0 (workflowStepType=1):
  * Manual: triggerType=2, triggerSubType="Manual", no notificationType
  * Notification: triggerType=0, notificationType in the allow-list; triggerSubType == notificationType
  * Scheduled: triggerType=2, triggerSubType="Scheduled", schedule object (see details below)
  * External: triggerType=1, triggerSubType non-empty, no notificationType
- After the trigger: a sequence of ACTIONs (workflowStepType=0) and optional CONDITIONs (workflowStepType=2).
- If actionType=15 (End Workflow), it MUST be the LAST step in that branch.

ACTION allow-list (numeric actionType): 1,2,9,14,15,19,20,21,22,23,24,25,26,31,32,33,34,35,36,37,38.

Notification allow-list (notificationType): SERVICE_STOP,SERVICE_MISSED,USER_LOGGED_IN,USER_LOGGED_OUT,LOW_MEMORY,HIGH_CPU_USAGE,HIGH_PING_TIME,PING_ERROR,LOW_HDD_FREE_SPACE,COMPUTER_OFFLINE,COMPUTER_BACK_ONLINE,PORT_NOT_AVAILABLE,EVENT_LOG_WATCH,REBOOT_REQUIRED,LOW_BATTERY,WINDOWS_UPDATES_AVAILABLE,PROCESS_STARTED,PROCESS_STOPPED,PERFORMANCE_COUNTER,APPLICATIONS_ADDED,USB_DEVICE_INSERT,USB_DEVICE_REMOVE,IP_CHANGED,USER_SUPPORT_REQUEST,WEB_SITE_ERROR,SNMP_ALERT,SECURITY_FIREWALL_DISABLED,SECURITY_ANTIVIRUS_DISABLED,HDD_SMART_FAILURE,ANTIVIRUS_DEFINITIONS_OUTDATED,COMPUTER_REGISTERED.

Scheduled trigger forms:
- Daily: schedule.frequencyInterval {uuid:1,id:1,text:"Daily"}, frequencySubinterval=0
- Weekly: frequencyInterval {uuid:4,id:2,text:"Weekly"}, frequencySubinterval is bitmask 1..127 (Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)
- Monthly: frequencyInterval {uuid:5,id:3,text:"Monthly"}, frequencySubinterval in [0,128,256]

Use ISO UTC for schedule.startDate like "YYYY-MM-DDTHH:MM:SS.mmmZ".
""")

USER_COMPILE_TMPL = """Specification (excerpt):
- Root key "workflowSteps" (array). First and only step 0 is a TRIGGER; then ACTIONs/CONDITIONs.
- Use only actionType in [1,2,9,14,15,19,20,21,22,23,24,25,26,27,31,32,33,34,35,36,37,38].
- For Notification triggers, notificationType in the allow-list and triggerSubType == notificationType.
- For Scheduled triggers, use the schedule forms exactly as shown.
- If End Workflow (actionType=15) is present, it MUST be last in that branch.

Few-shots:
{fewshots}

User request:
{request}

Before emitting, ensure:
- [ ] trigger is step 0 and unique, all steps have id, no forbidden keys, all refs/resolved.
Return JSON only, wrapped between <json> and </json>.
"""

USER_CRITIC_TMPL = """User request:
{request}

Candidate JSON:
{candidate}

Validation errors:
{errors}

Before emitting, ensure:
- [ ] trigger is step 0 and unique, all steps have id, no forbidden keys, all refs/resolved.
Return corrected JSON ONLY.
"""

USER_PARAPHRASE_TMPL = """
GOAL:
{goal}

SCOPE (which devices/sites/users or policies it applies to):
{scope}

INPUT/OUTPUT VIEW (key checks, actions, and resulting logs/alerts/tickets/changes):
{input}
"""

USER_SABOTAGER_TMPL = """Generate a proper RMM automation workflow in JSON format.

Few-shots:
{fewshots}

User request:
{request}

Return JSON only, wrapped between <json> and </json>.
"""

FEWSHOTS_TEXT = """
<example>
// Minimal manual trigger + OS type gate + cleanup, with End in negative branch
<json>
{
   "workflowSteps": [
      {
         "displayName": "Ad-hoc",
         "id": 1001,
         "skipOffline": false,
         "triggerSubType": "Manual",
         "triggerType": 2,
         "workflowStepType": 1
      },
      {
         "displayName": "Is this a Windows OS?",
         "negativeOutcome": [
            {
               "actionType": 22,
               "displayName": "Write Log: Not Windows",
               "parameters": {
                  "message": "This is not a Windows device. Ending workflow as Success.",
                  "variables": []
               },
               "workflowStepType": 0
            },
            {
               "actionType": 15,
               "displayName": "End Workflow",
               "parameters": {
                  "status": 2
               },
               "workflowStepType": 0
            }
         ],
         "positiveOutcome": [
            {
               "actionType": 36,
               "displayName": "Execute Powershell: Clear Temp",
               "parameters": {
                  "captureOutput": false,
                  "commandLine": "Remove-Item -Path \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue",
                  "executeAsSystem": true,
                  "outputVariable": "TempCleanupResult",
                  "variables": []
               },
               "workflowStepType": 0
            }
         ],
         "ruleAggregation": 0,
         "rules": [
            {
               "operator": 2,
               "propertyId": "oSType",
               "value": 1,
               "workflowStepId": 1001
            }
         ],
         "workflowStepType": 2
      }
   ]
}
</json>
</example>

<example>
// Variable produced by Powershell (36) → used in a rule, rule.workflowStepId points to producer; VarRef used in Log
<json>
{
   "workflowSteps": [
      {
         "displayName": "Ad-hoc",
         "id": 2001,
         "skipOffline": true,
         "triggerSubType": "Manual",
         "triggerType": 2,
         "workflowStepType": 1
      },
      {
         "actionType": 36,
         "displayName": "Check Low Disk (C:)",
         "id": 2002,
         "parameters": {
            "captureOutput": true,
            "commandLine": "if(((Get-Volume -DriveLetter C).SizeRemaining/1GB) -lt 10){'True'}else{'False'}",
            "executeAsSystem": true,
            "outputVariable": "LowDisk",
            "variables": []
         },
         "workflowStepType": 0
      },
      {
         "displayName": "Is C: below 10GB?",
         "negativeOutcome": [
            {
               "actionType": 22,
               "displayName": "Write Log: Enough Space",
               "parameters": {
                  "message": "Disk space OK.",
                  "variables": []
               },
               "workflowStepType": 0
            }
         ],
         "positiveOutcome": [
            {
               "actionType": 22,
               "displayName": "Write Log: Low Disk",
               "parameters": {
                  "message": "Low disk space detected on C:. Flag: #1719471831001",
                  "variables": [
                     {
                        "displayName": "LowDisk",
                        "propertyId": "variable",
                        "sourceId": "LowDisk",
                        "type": 2,
                        "variableId": "1719471831001",
                        "workflowStepId": 0,
                        "workflowStepName": "Variable"
                     }
                  ]
               },
               "workflowStepType": 0
            }
         ],
         "ruleAggregation": 0,
         "rules": [
            {
               "operator": 0,
               "propertyId": "Variable",
               "value": "True",
               "variablesId": "LowDisk",
               "variablesType": 0,
               "workflowStepId": 2002
            }
         ],
         "workflowStepType": 2
      }
   ]
}
</json>
</example>

<example>
// Scheduled weekly trigger (bitmask days), rule using scope with correct scopeId/name pair
<json>
{
   "workflowSteps": [
      {
         "displayName": "Scheduled weekly",
         "id": 4001,
         "schedule": {
            "frequency": 1,
            "frequencyInterval": {
               "id": 2,
               "text": "Weekly",
               "uuid": 4
            },
            "frequencySubinterval": 10,
            "startDate": "2025-01-01T09:00:00.000Z",
            "timezone": "UTC"
         },
         "skipOffline": false,
         "triggerSubType": "Scheduled",
         "triggerType": 2,
         "workflowStepType": 1
      },
      {
         "displayName": "Is this a Windows 11 device?",
         "negativeOutcome": [
            {
               "actionType": 22,
               "displayName": "Write Log: Scope not matched",
               "parameters": {
                  "message": "Skipped: not Windows 11.",
                  "variables": []
               },
               "workflowStepType": 0
            }
         ],
         "positiveOutcome": [
            {
               "actionType": 36,
               "displayName": "Execute Powershell: Weekly maintenance",
               "parameters": {
                  "captureOutput": true,
                  "commandLine": "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object -First 1",
                  "executeAsSystem": true,
                  "outputVariable": "MaintResult",
                  "variables": []
               },
               "workflowStepType": 0
            }
         ],
         "ruleAggregation": 0,
         "rules": [
            {
               "computerIds": [],
               "operator": 2,
               "propertyId": "scope",
               "scopeId": -15,
               "scopeName": "All Windows 11 Computers",
               "workflowStepId": 4001
            }
         ],
         "workflowStepType": 2
      }
   ]
}
</json>
</example>

<example>
// Get and log Bitlocker and TPM status for Windows 10 and Windows 11 devices
<json>
{
  "workflowSteps": [
    {
      "triggerType": 2,
      "triggerSubType": "Manual",
      "skipOffline": false,
      "workflowStepType": 1,
      "displayName": "Ad-hoc"
    },
    {
      "workflowStepType": 2,
      "positiveOutcome": [
        {
          "workflowStepType": 0,
          "actionType": 36,
          "parameters": {
            "commandLine": "(Get-BitLockerVolume -MountPoint \\\"$Env:SystemDrive\\\").ProtectionStatus",
            "executeAsSystem": true,
            "captureOutput": true,
            "outputVariable": "BitLocker Status",
            "variables": []
          },
          "displayName": "Execute Powershell: Get BitLocker status"
        },
        {
          "workflowStepType": 0,
          "actionType": 36,
          "parameters": {
            "commandLine": "Get-WmiObject -Namespace \\\"Root\\\\CIMv2\\\\Security\\\\MicrosoftTpm\\\" -Class Win32_Tpm",
            "executeAsSystem": true,
            "captureOutput": true,
            "outputVariable": "TPM Status",
            "variables": []
          },
          "displayName": "Execute Powershell: Get TPM status"
        },
        {
          "workflowStepType": 2,
          "positiveOutcome": [
            {
              "workflowStepType": 0,
              "actionType": 22,
              "parameters": {
                "message": "Get BitLocker Status: #1719471831002\\nTPM Status: #1719559801096\\n",
                "variables": [
                  {
                    "variableId": "1719471831002",
                    "propertyId": "variable",
                    "workflowStepId": 0,
                    "sourceId": "BitLocker Status",
                    "displayName": "BitLocker Status",
                    "type": 2,
                    "workflowStepName": "Variable"
                  },
                  {
                    "variableId": "1719559801096",
                    "propertyId": "variable",
                    "workflowStepId": 0,
                    "sourceId": "TPM Status",
                    "displayName": "TPM Status",
                    "type": 2,
                    "workflowStepName": "Variable"
                  }
                ]
              },
              "displayName": "Write Log: BitLocker is On"
            }
          ],
          "negativeOutcome": [
            {
              "workflowStepType": 0,
              "actionType": 22,
              "parameters": {
                "message": "Get BitLocker Status: #1719471830719\\nTPM Status: #1719559801139\\n",
                "variables": [
                  {
                    "variableId": "1719471830719",
                    "propertyId": "variable",
                    "workflowStepId": 0,
                    "sourceId": "BitLocker Status",
                    "displayName": "BitLocker Status",
                    "type": 2,
                    "workflowStepName": "Variable"
                  },
                  {
                    "variableId": "1719559801139",
                    "propertyId": "variable",
                    "workflowStepId": 0,
                    "sourceId": "TPM Status",
                    "displayName": "TPM Status",
                    "type": 2,
                    "workflowStepName": "Variable"
                  }
                ]
              },
              "displayName": "Write Log: BitLocker is Off/Unknown"
            }
          ],
          "ruleAggregation": 0,
          "rules": [
            {
              "variablesId": "BitLocker Status",
              "variablesType": 0,
              "value": "On",
              "propertyId": "Variable",
              "operator": 0
            }
          ],
          "displayName": "Is BitLocker status On?"
        }
      ],
      "negativeOutcome": [
        {
          "workflowStepType": 0,
          "actionType": 22,
          "parameters": {
            "message": "Get BitLocker Status: This is not a Windows 10/11 device. Nothing to do. Ending Workflow as Success.",
            "variables": []
          },
          "displayName": "Write Log: This is not a Windows 10/11 device"
        },
        {
          "workflowStepType": 0,
          "actionType": 15,
          "parameters": { "status": 2 },
          "id": 1709560606184,
          "displayName": "End Workflow"
        }
      ],
      "ruleAggregation": 1,
      "rules": [
        {
          "scopeName": "All Windows 10 Computers",
          "computerIds": [],
          "workflowStepId": 1707756270839,
          "propertyId": "scope",
          "operator": 2,
          "scopeId": -14
        },
        {
          "scopeName": "All Windows 11 Computers",
          "computerIds": [],
          "workflowStepId": 1707756270839,
          "propertyId": "scope",
          "operator": 2,
          "scopeId": -15
        }
      ],
      "displayName": "Is this a Windows 10/11 device?"
    }
  ]
}
</json>
</example>

<example>
// Disk cleaning workflow
<json>
{
  "workflowSteps": [
   {
      "displayName": "Ad-hoc",
      "id": 1752662439291,
      "skipOffline": true,
      "triggerSubType": "Manual",
      "triggerType": 2,
      "workflowStepType": 1
   },
   {
      "actionType": 36,
      "displayName": "Check Disk Space",
      "id": 1752662439292,
      "parameters": {
         "captureOutput": true,
         "commandLine": "Get-PSDrive -PSProvider FileSystem | Select-Object -Property Name, @{Name='FreeSpace';Expression={[math]::Round($_.Free / 1GB, 2)}}, @{Name='TotalSize';Expression={[math]::Round($_.Used / 1GB, 2) + [math]::Round($_.Free / 1GB, 2)}}\n$freeSpace = (Get-PSDrive -PSProvider FileSystem).Free / (Get-PSDrive -PSProvider FileSystem).Total * 100\n$threshold = 10\n$belowThreshold = $freeSpace -lt $threshold\n$belowThreshold",
         "executeAsSystem": true,
         "outputVariable": "belowThreshold",
         "variables": []
      },
      "workflowStepType": 0
   },
   {
      "displayName": "Is Disk Space Below Threshold?",
      "id": 1752662439293,
      "negativeOutcome": [
         {
            "actionType": 22,
            "displayName": "Log No Cleanup Needed",
            "id": 1752662439299,
            "parameters": {
               "message": "Disk space is above the threshold. No cleanup performed.",
               "variables": []
            },
            "workflowStepType": 0
         }
      ],
      "positiveOutcome": [
         {
            "actionType": 36,
            "displayName": "Cleanup Temp Files, Windows Update Cache, and Log Files",
            "id": 1752662439294,
            "parameters": {
               "captureOutput": false,
               "commandLine": "Remove-Item -Path $env:TEMP\\* -Recurse -Force\nRemove-Item -Path C:\\Windows\\Temp\\* -Recurse -Force\nRemove-Item -Path C:\\Windows\\SoftwareDistribution\\* -Recurse -Force\nRemove-Item -Path C:\\Windows\\Logs\\* -Recurse -Force",
               "executeAsSystem": true,
               "outputVariable": "CleanupResult",
               "variables": []
            },
            "workflowStepType": 0
         },
         {
            "actionType": 36,
            "displayName": "Check Disk Space After Cleanup",
            "id": 1752662439295,
            "parameters": {
               "captureOutput": true,
               "commandLine": "Get-PSDrive -PSProvider FileSystem | Select-Object -Property Name, @{Name='FreeSpace';Expression={[math]::Round($_.Free / 1GB, 2)}}, @{Name='TotalSize';Expression={[math]::Round($_.Used / 1GB, 2) + [math]::Round($_.Free / 1GB, 2)}}\n$freeSpace = (Get-PSDrive -PSProvider FileSystem).Free / (Get-PSDrive -PSProvider FileSystem).Total * 100\n$threshold = 10\n$belowThreshold = $freeSpace -lt $threshold\n$belowThreshold",
               "executeAsSystem": true,
               "outputVariable": "belowThresholdAfterCleanup",
               "variables": []
            },
            "workflowStepType": 0
         },
         {
            "displayName": "Is Disk Space Below Threshold After Cleanup?",
            "id": 1752662439296,
            "negativeOutcome": [
               {
                  "actionType": 22,
                  "displayName": "Log Failure",
                  "id": 1752662439298,
                  "parameters": {
                     "message": "Disk Cleanup Unsuccessful: Disk space is still below the threshold. Initial disk space: #1719471831002 GB, Final disk space: #1719559801096 GB, Cleanup actions attempted: Temp files, Windows Update Cache, Log Files",
                     "variables": [
                        {
                           "displayName": "belowThreshold",
                           "propertyId": "variable",
                           "sourceId": "belowThreshold",
                           "type": 2,
                           "variableId": "1719471831002",
                           "workflowStepId": 0,
                           "workflowStepName": "Variable"
                        },
                        {
                           "displayName": "belowThresholdAfterCleanup",
                           "propertyId": "variable",
                           "sourceId": "belowThresholdAfterCleanup",
                           "type": 2,
                           "variableId": "1719559801096",
                           "workflowStepId": 0,
                           "workflowStepName": "Variable"
                        }
                     ]
                  },
                  "workflowStepType": 0
               }
            ],
            "positiveOutcome": [
               {
                  "actionType": 22,
                  "displayName": "Log Success",
                  "id": 1752662439297,
                  "parameters": {
                     "message": "Disk Cleanup Successful: Disk space is now above the threshold. Space recovered: #1719471831002 GB",
                     "variables": [
                        {
                           "displayName": "belowThresholdAfterCleanup",
                           "propertyId": "variable",
                           "sourceId": "belowThresholdAfterCleanup",
                           "type": 2,
                           "variableId": "1719471831002",
                           "workflowStepId": 0,
                           "workflowStepName": "Variable"
                        }
                     ]
                  },
                  "workflowStepType": 0
               }
            ],
            "ruleAggregation": 0,
            "rules": [
               {
                  "operator": 0,
                  "propertyId": "Variable",
                  "value": "True",
                  "variablesId": "belowThresholdAfterCleanup",
                  "variablesType": 0,
                  "workflowStepId": 0
               }
            ],
            "workflowStepType": 2
         }
      ],
      "ruleAggregation": 0,
      "rules": [
         {
            "operator": 0,
            "propertyId": "Variable",
            "value": "True",
            "variablesId": "belowThreshold",
            "variablesType": 0,
            "workflowStepId": 0
         }
      ],
      "workflowStepType": 2
   },
   {
      "actionType": 15,
      "displayName": "End Workflow",
      "id": 1752662439300,
      "parameters": {
         "status": 2
      },
      "workflowStepType": 0
   }
  ]
}
</json>
</example>
""".strip()
