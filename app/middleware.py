import uuid
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

class HostingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle user-specific sessions and storage constraints.
    Enabled only when settings.HOSTING is True.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Enforce file size limit for POST requests if HOSTING is enabled
        if settings.HOSTING and request.method == "POST":
            content_length = request.headers.get("Content-Length")
            if content_length and int(content_length) > settings.MAX_FILE_SIZE:
                logger.warning(f"Rejected request due to size: {content_length} bytes")
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"File too large. Maximum size allowed is {settings.MAX_FILE_SIZE / (1024*1024):.0f}MB."
                    }
                )

        # 2. Manage user_id cookie if HOSTING is enabled
        user_id = None
        is_new_user = False
        
        if settings.HOSTING:
            user_id = request.cookies.get("user_id")
            if not user_id:
                user_id = str(uuid.uuid4())
                is_new_user = True
            
            # Attach user_id to request state for use in endpoints
            request.state.user_id = user_id
        else:
            request.state.user_id = None

        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"Error in middleware dispatch: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error in middleware"}
            )

        # 3. Set cookie on response for new users if HOSTING is enabled
        if settings.HOSTING and is_new_user:
            response.set_cookie(
                key="user_id",
                value=user_id,
                # Cookie expires when project expires (30 days)
                max_age=settings.PROJECT_EXPIRY_DAYS * 24 * 3600,
                httponly=True,
                samesite="lax",
                # Secure=True would be better but requires HTTPS
                # secure=True 
            )

        return response
