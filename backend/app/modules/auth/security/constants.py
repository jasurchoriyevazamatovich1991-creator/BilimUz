"""
No magic numbers. NOTE — deliberate policy difference from the top-level
`app/modules/auth/constants.py` (PASSWORD_MIN_LENGTH there = 12): this
Sprint 3 spec asked for 10. Both constants currently exist in the
codebase; see security/README.md "Known conflict" section — reconciling
them is a follow-up step, not done here per the "stop after PasswordService"
instruction.
"""
import re

PASSWORD_MIN_LENGTH = 10

UPPER_RE = re.compile(r"[A-Z]")
LOWER_RE = re.compile(r"[a-z]")
DIGIT_RE = re.compile(r"\d")
SPECIAL_RE = re.compile(r"[!@#$%^&*()\-_=+\[\]{};:,.<>/?]")

ARGON2_TIME_COST = 3        # passlib default is 2; 3 balances security/latency for a login-path hash
ARGON2_MEMORY_COST = 65536  # 64 MB
ARGON2_PARALLELISM = 4
