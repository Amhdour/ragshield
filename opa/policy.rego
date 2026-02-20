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

# citation references unknown doc/chunk
deny[reason] {
  citation := input.citations[_]
  citation.doc_id != ""
  citation.chunk_id != ""
  not known_chunk(citation.doc_id, citation.chunk_id)
  reason := sprintf("Unknown citation target: %v/%v", [citation.doc_id, citation.chunk_id])
}

# quote not found in cited chunk text
deny[reason] {
  citation := input.citations[_]
  known_chunk(citation.doc_id, citation.chunk_id)
  citation.quote != ""
  not quote_in_chunk(citation.doc_id, citation.chunk_id, citation.quote)
  reason := sprintf("Citation quote not found in chunk: %v/%v", [citation.doc_id, citation.chunk_id])
}

known_chunk(doc_id, chunk_id) {
  chunk := input.context_chunks[_]
  chunk.doc_id == doc_id
  chunk.chunk_id == chunk_id
}

quote_in_chunk(doc_id, chunk_id, quote) {
  chunk := input.context_chunks[_]
  chunk.doc_id == doc_id
  chunk.chunk_id == chunk_id
  contains(lower(chunk.text), lower(quote))
}

allow {
  count(deny) == 0
}

reasons := [reason | deny[reason]]

# -----------------------------------------------------------------------------
# Pre-action policy pack
# Inputs expected:
# - action: retrieval|llm|return_answer|debug
# - requested_data_scope: knowledge_base|sensitive|admin
# - user_role: user|admin
# - risk_flags: {injection_suspected: bool, exfil_suspected: bool}
# - response_is_refusal: bool (used for return_answer when exfil risk is present)
# -----------------------------------------------------------------------------

deny_action[reason] {
  input.requested_data_scope == "sensitive"
  input.user_role != "admin"
  reason := "Pre-action denied: sensitive scope requires admin role"
}

# Normal users can only retrieve from knowledge_base.
deny_action[reason] {
  input.action == "retrieval"
  input.user_role != "admin"
  input.requested_data_scope != "knowledge_base"
  reason := "Pre-action denied: normal users may retrieve only knowledge_base scope"
}

# Exfil risk blocks all actions except returning an explicit refusal.
deny_action[reason] {
  input.risk_flags.exfil_suspected
  input.action != "return_answer"
  reason := "Pre-action denied: exfiltration risk"
}

deny_action[reason] {
  input.risk_flags.exfil_suspected
  input.action == "return_answer"
  not input.response_is_refusal
  reason := "Pre-action denied: exfiltration risk requires refusal response"
}

# Injection risk disallows debug actions for all roles.
deny_action[reason] {
  input.risk_flags.injection_suspected
  input.action == "debug"
  reason := "Pre-action denied: injection risk blocks debug action"
}

allow_action {
  count(deny_action) == 0
}

action_reasons := [reason | deny_action[reason]]
