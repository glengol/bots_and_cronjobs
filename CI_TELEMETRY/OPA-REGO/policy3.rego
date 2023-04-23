package example_policy

default allow = false

example_tags[tag] {
    tag := input.tags[_]
    contains(tag, "example")
}

allow {
    example_tags[_]
}
