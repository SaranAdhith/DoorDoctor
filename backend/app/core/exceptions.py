"""Consistent HTTP errors. Every response body is `{"detail": "..."}`."""

from fastapi import HTTPException, status


class AppError(HTTPException):
    """Base class so services can raise transport-agnostic, message-first errors."""

    status_code_default = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        super().__init__(status_code=status_code or self.status_code_default, detail=detail)


class BadRequestError(AppError):
    status_code_default = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(AppError):
    status_code_default = status.HTTP_401_UNAUTHORIZED

    def __init__(self, detail: str = "Not authenticated.") -> None:
        super().__init__(detail)
        self.headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code_default = status.HTTP_403_FORBIDDEN

    def __init__(self, detail: str = "You do not have permission to perform this action.") -> None:
        super().__init__(detail)


class NotFoundError(AppError):
    status_code_default = status.HTTP_404_NOT_FOUND

    def __init__(self, detail: str = "Resource not found.") -> None:
        super().__init__(detail)


class ConflictError(AppError):
    status_code_default = status.HTTP_409_CONFLICT
