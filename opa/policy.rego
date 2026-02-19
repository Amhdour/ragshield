package ragshield

default allow = false

deny[msg] {
  answer := lower(input.answer)
  contains(answer, "system prompt")
  msg := "Possible system prompt disclosure"
}

deny[msg] {
  answer := lower(input.answer)
  contains(answer, "system message")
  msg := "Possible system message disclosure"
}

deny[msg] {
  answer := lower(input.answer)
  contains(answer, "sk-")
  msg := "Possible secret/token pattern (sk-)"
}

deny[msg] {
  answer := lower(input.answer)
  contains(answer, "token=")
  msg := "Possible secret/token pattern (token=)"
}

deny[msg] {
  answer := lower(input.answer)
  contains(answer, "apikey")
  msg := "Possible secret/token pattern (apikey)"
}

deny[msg] {
  confidence := lower(input.confidence)
  confidence == "med" or confidence == "high"
  count(input.citations) == 0
  msg := "Citations missing for med/high confidence"
}

allow {
  count(deny) == 0
}

reasons := [reason | deny[reason]]
