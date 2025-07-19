from fastapi import APIRouter, Depends
from models.blog import blog_posts_collection
from auth import get_current_user
from qr_utils import slugify
from settings import ADMIN, BASE_URL
from models.blog import BlogPost
import logging

logger = logging.getLogger("app_logger")

router = APIRouter(prefix="/api")


def extract_annotations(choice):
    annotations = getattr(choice.message, "annotations", [])
    links = []
    for ann in annotations:
        if ann.type == "url_citation" and hasattr(ann, "url_citation"):
            url_data = ann.url_citation
            title = getattr(url_data, "title", None)
            url = getattr(url_data, "url", None)
            if title and url:
                links.append({title: url})
    return links

async def create_blog_post(post: BlogPost) -> dict:
    post.slug = slugify(post.title)

    existing = await blog_posts_collection.find_one({"slug": post.slug})
    if existing:
        logger.info(f"Пост {post.title} уже существует")
        return {
            "status": "error",
            "slug": post.slug,
            "message": "Пост с таким заголовком уже существует"
        }

    # Генерация ссылки на изображение
    if not post.image_link:
        post.image_link = f"{BASE_URL}/static/img/posts/{post.slug}.jpg"

    await blog_posts_collection.insert_one(post.dict())
    logger.info(f"Пост {post.title} успешно опубликован")
    return {"status": "ok", "slug": post.slug}





async def get_latest_post():
    return await blog_posts_collection.find_one({}, sort=[("date", -1)])

async def get_all_post_titles():
    return await blog_posts_collection.find({}, {"title": 1, "slug": 1}).to_list(500)

async def get_post_by_slug(slug: str):
    return await blog_posts_collection.find_one({"slug": slug})


@router.post("/create/")
async def create_post(post: BlogPost, user: dict = Depends(get_current_user)):
    if user.get("email") != ADMIN:
        logger.info(f"Пост {post.title} не удалось опубликовать")
        return {"status": "error", "message": "Access denied"}
    logger.info(f"Пост {post.title} успешно опубликован")
    return await create_blog_post(post)
    # if user and user.get("email") == ADMIN:
    #     post.slug = slugify(post.title)
    #
    #     existing = await blog_posts_collection.find_one({"slug": post.slug})
    #     if existing:
    #         return {
    #             "status": "error",
    #             "slug": post.slug,
    #             "message": "Пост с таким заголовком уже существует"
    #         }
    #
    #     post_dict = post.dict()
    #     await blog_posts_collection.insert_one(post_dict)
    #     return {"status": "ok", "slug": post.slug}
    # else:
    #     return {
    #         "status": "error",
    #         "message": "Access denied"
    #     }

# async def create_indexes():
#     await blog_posts_collection.create_index([("slug", 1)], unique=True)
#     await blog_posts_collection.create_index([("date", -1)])
#     print("Индексы успешно созданы.")
#
# if __name__ == "__main__":
#     asyncio.run(create_indexes())