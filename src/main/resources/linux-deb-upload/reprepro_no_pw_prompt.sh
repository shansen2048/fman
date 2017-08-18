#!/usr/bin/expect -f

set timeout 2
set gpg_pass [lindex $argv 0]

spawn reprepro --ask-passphrase -b [lindex $argv 1] --confdir {*}[lrange $argv 2 end]

expect {
    "*passphrase:*" {
        send -- "${gpg_pass}\r"
    }
}
expect {
    "*passphrase:*" {
        send -- "${gpg_pass}\r"
    }
}
interact