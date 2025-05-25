from fastapi import APIRouter
admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.post("/delete-chat")
async def delete_chat_route(*args):
   pass
