# Security policy

## Supported versions

Only the latest release on PyPI receives fixes. Upgrade with
`uv tool upgrade t1-bootstrap` or `pipx upgrade t1-bootstrap`.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting at
<https://github.com/tabelle1/t1-bootstrap/security/advisories/new>, or email
<hello@tabelle1.at>. You will hear back within a week.

## What t1 runs on your machine

t1 writes files into a directory you named and then runs `uv` and `git` there.
Only after you say yes - or run `t1 install-uv` yourself - does it fetch Astral's
official uv installer (`install.sh` on macOS and Linux, `install.ps1` on Windows)
into a temporary file and run it from there. Nothing runs through a shell string
assembled at runtime, and nothing is downloaded or executed without a prompt.
