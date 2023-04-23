package ec2

default allow = false

is_t2_micro {
    input.instanceType == "t2.micro"
}

allow {
    is_t2_micro
}
