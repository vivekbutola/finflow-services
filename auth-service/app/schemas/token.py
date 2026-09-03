from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenPayload(BaseModel):
    sub: str
    type: str
    iat: int
    exp: int
    jti: str
    iss: str
    aud: str
