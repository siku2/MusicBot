"""Webiesela Exceptions."""

import enum


class Exceptions(enum.IntEnum):
    """An enumeration with all the exceptions."""

    TOKEN_UNKNOWN = 1000
    TOKEN_EXPIRED = 1001
    REGISTRATION_TOKEN_EXPIRED = 1002
    ALREADY_AUTHORISED = 1003

    MISSING_PARAMS = 2000
