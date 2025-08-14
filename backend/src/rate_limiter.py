from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from src.config import settings
from jose import jwt, JWTError


def get_user_key(request: Request) -> str:
    """
    Generate a unique key for the user for rate limiting.
    It attempts to use the user's identifier from the JWT token.
    If the token is not present or invalid, it falls back to the remote IP address.
    """
    try:
        # L'en-tête est de la forme "Bearer <token>"
        auth_header = request.headers.get("authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            # Décoder le token pour obtenir le 'sub' (email de l'utilisateur)
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("sub")
            if user_id:
                return str(user_id)
    except (JWTError, KeyError, IndexError):
        # En cas d'erreur de token ou de header manquant, on se rabat sur l'IP
        pass
    # Fallback pour les utilisateurs non authentifiés ou en cas d'erreur
    return get_remote_address(request)


# Initialize the Limiter with Redis storage and the user key function
limiter = Limiter(
    key_func=get_user_key,
    storage_uri=settings.REDIS_URL,
    default_limits=[f"{settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_TIMESCALE_MINUTES} minutes"]
)