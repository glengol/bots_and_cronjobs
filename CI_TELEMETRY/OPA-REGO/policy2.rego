package example.aws

import input

default allow = false

deny {
    value := input.configuration[_]
    contains(value, "example")
}

allow {
    not deny
}
