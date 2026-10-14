from __future__ import annotations


class IronkitError(Exception):
    pass


class FailSafeError(IronkitError):
    pass


class ImageNotFoundError(IronkitError):
    pass


class WindowNotFoundError(IronkitError):
    pass


class InvalidKeyError(IronkitError, ValueError):
    pass


class UnsupportedFeatureError(IronkitError):
    pass


class BackendError(IronkitError):
    pass


class UnsupportedPlatformError(BackendError):
    pass


class PermissionDeniedError(BackendError):
    pass
