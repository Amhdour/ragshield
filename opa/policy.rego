package ragshield

import future.keywords.in

default allow = true
default allow_action = true

# Post-response guardrails (defense in depth)
deny[reason] {
  answer := lower(input.answer)
  contains(answer, "system prompt")
  reason := "Potential system prompt disclosure"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "developer message")
  reason := "Potential developer message disclosure"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "hidden instructions")
  reason := "Potential hidden instructions disclosure"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "internal instructions")
  reason := "Potential internal instructions disclosure"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "here is the system prompt")
  reason := "Explicit system prompt disclosure attempt"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "i will reveal")
  contains(answer, "system prompt")
  reason := "Explicit intent to reveal system prompt"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "i will reveal")
  contains(answer, "developer message")
  reason := "Explicit intent to reveal developer message"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "sk-")
  reason := "Potential secret pattern detected (sk-)"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "token=")
  reason := "Potential secret pattern detected (token=)"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "apikey")
  reason := "Potential secret pattern detected (apikey)"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "api_key")
  reason := "Potential secret pattern detected (api_key)"
}

deny[reason] {
  answer := lower(input.answer)
  contains(answer, "authorization: bearer")
  reason := "Potential secret pattern detected (Authorization: Bearer)"
}

deny[reason] {
  confidence := lower(input.confidence)
  confidence in {"med", "high"}
  count(input.citations) == 0
  reason := "Citations missing for med/high confidence"
}

allow {
  count(deny) == 0
}

reasons := [reason | deny[reason]]

# Pre-action policy: block unsafe tool invocation before execution.
prompt_injection_query {
  q := lower(input.user_query)
  contains(q, "ignore previous")
}

prompt_injection_query {
  q := lower(input.user_query)
  contains(q, "jailbreak")
}

prompt_injection_query {
  q := lower(input.user_query)
  contains(q, "developer message")
}

data_exfil_query {
  q := lower(input.user_query)
  contains(q, "system prompt")
}

data_exfil_query {
  q := lower(input.user_query)
  contains(q, "secret_internal")
}

data_exfil_query {
  q := lower(input.user_query)
  contains(q, "apikey")
}

data_exfil_query {
  q := lower(input.user_query)
  contains(q, "token=")
}

data_exfil_query {
  q := lower(input.user_query)
  contains(q, "sk-")
}

deny_action[reason] {
  prompt_injection_query
  input.action != "retrieval"
  reason := "Pre-action denied: prompt injection risk, only retrieval allowed"
}

deny_action[reason] {
  data_exfil_query
  input.action != "retrieval"
  reason := "Pre-action denied: exfiltration risk, only retrieval allowed"
}

allow_action {
  count(deny_action) == 0
}

action_reasons := [reason | deny_action[reason]]
