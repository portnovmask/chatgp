from fastapi import APIRouter

router = APIRouter()

@router.get("/products")
async def get_products():
    return {"products": ["Товар 1", "Товар 2", "Товар 3"]}
