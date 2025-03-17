from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from models.users import users_collection
from models.user_data import users_data_collection
from auth import get_current_user

router = APIRouter()

@router.get("/dashboard")
async def dashboard(request: Request, user=Depends(get_current_user)):
    """Кабинет пользователя"""
    if not user:
        return RedirectResponse(url="/authorize")
    me_data = await users_data_collection.find_one({"email": user.get("email")})
    return me_data
