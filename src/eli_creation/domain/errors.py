# Reused from ELI_Legal: src/eli_legal/domain/errors.py @ 3b05ccd88f. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
class EliCreationError(Exception):
    """Base domain error."""


class PolicyDenied(EliCreationError):
    pass


class MatterAccessDenied(EliCreationError):
    pass


class AuthenticationFailed(EliCreationError):
    pass


class StepUpRequired(AuthenticationFailed):
    """Signed in, but this decision needs the passphrase again."""


class AccountLocked(AuthenticationFailed):
    """Too many failed attempts. The account is refused until the lock expires or is lifted."""


class SecondFactorRequired(AuthenticationFailed):
    """The passphrase was right; the code from the person's authenticator is still needed."""


class VerificationGateFailed(EliCreationError):
    pass


class AuditIntegrityError(EliCreationError):
    pass


class MissingAuditKey(AuditIntegrityError):
    pass


class DatabaseKeyError(AuditIntegrityError):
    """A database cannot be opened with the key it was encrypted with: the key is wrong or
    missing, or SQLCipher is not there to read it. Never answered with a new, empty database."""


class NetworkDenied(EliCreationError):
    """Outbound network use that the approved-source policy does not permit."""


class NotFound(EliCreationError):
    pass


class InvalidState(EliCreationError):
    """An operation was attempted in a lifecycle state that does not allow it."""


class IngestionError(EliCreationError):
    pass


class UnsupportedDocument(IngestionError):
    pass


class InferenceUnavailable(EliCreationError):
    pass


class ConnectorError(EliCreationError):
    pass


class HoldRaised(EliCreationError):
    """Raised by a workflow step to stop itself and everything that depends on it."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


class EntitlementDenied(EliCreationError):
    """The hosting ELI licence does not entitle this edition."""


class InvalidInput(EliCreationError, ValueError):
    """The request is missing something a governed action requires, such as a reason."""


class RunStopped(EliCreationError):
    """A person stopped the run while a step was working; the step ends where it is."""
