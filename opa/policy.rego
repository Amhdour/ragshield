package ragshield

# Default deny if any safety condition is not met.
default allow := false

allow if {
  not blocked_query
  not blocked_response
}

blocked_query if {
  contains(lower(input.query), "ignore previous instructions")
}

blocked_response if {
  contains(lower(input.response), "api key")
}
