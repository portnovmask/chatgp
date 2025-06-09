# import asyncio

from fastapi import APIRouter, Request, Depends
# from fastapi.responses import RedirectResponse
from models.blog import blog_posts_collection
# from models.user_data import users_data_collection
from auth import get_current_user
from qr_utils import slugify
from typing import Optional


router = APIRouter(prefix="/api")

from pydantic import BaseModel

class BlogPost(BaseModel):
    title: str
    description: str
    content: str
    author: str
    date: str
    image_link: str
    annotations: list[str]
    slug: Optional[str] = None








async def get_latest_post():
    return await blog_posts_collection.find_one({}, sort=[("date", -1)])

async def get_all_post_titles():
    return await blog_posts_collection.find({}, {"title": 1, "slug": 1}).to_list(500)

async def get_post_by_slug(slug: str):
    return await blog_posts_collection.find_one({"slug": slug})


@router.post("/create/")
async def create_post(post: BlogPost, user: dict = Depends(get_current_user)):
    if user and user.get("email") == "restrnx@yandex.ru":
        post.slug = slugify(post.title)

        existing = await blog_posts_collection.find_one({"slug": post.slug})
        if existing:
            return {
                "status": "error",
                "slug": post.slug,
                "message": "Пост с таким заголовком уже существует"
            }

        post_dict = post.dict()
        await blog_posts_collection.insert_one(post_dict)
        return {"status": "ok", "slug": post.slug}
    else:
        return {
            "status": "error",
            "message": "Access denied"
        }

# async def create_indexes():
#     await blog_posts_collection.create_index([("slug", 1)], unique=True)
#     await blog_posts_collection.create_index([("date", -1)])
#     print("Индексы успешно созданы.")
#
# if __name__ == "__main__":
#     asyncio.run(create_indexes())