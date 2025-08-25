from fastapi import APIRouter, Depends
from models.blog import blog_posts_collection
from auth import get_current_user
from qr_utils import slugify
from settings import ADMIN, BASE_URL
from models.blog import BlogPost
import logging
from datetime import datetime, timezone
from pathlib import Path

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



STATIC_PAGES = ["/", "/about", "/policy", "/help", "/price"]
SITEMAP_PATH = Path("static/sitemap.xml")

async def update_sitemap(new_slug: str):
    """
    Добавляет новый пост в sitemap.xml, создаёт файл, если его нет.
    """
    urls = STATIC_PAGES + [f"/post/{new_slug}"]

    # Если файл существует, читаем уже существующие записи
    if SITEMAP_PATH.exists():
        import xml.etree.ElementTree as ET
        tree = ET.parse(SITEMAP_PATH)
        root = tree.getroot()
        existing_urls = {el.find("loc").text for el in root.findall("url")}
        urls = [url for url in urls if f"{BASE_URL}{url}" not in existing_urls]
    else:
        # Создаём корень
        SITEMAP_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not urls:
        return  # всё уже есть

    # Генерируем XML
    from xml.sax.saxutils import escape
    lines = []
    if not SITEMAP_PATH.exists():
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(BASE_URL + url)}</loc>")
        lines.append(f"    <lastmod>{datetime.now(timezone.utc).date()}</lastmod>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.8</priority>")
        lines.append("  </url>")

    if not SITEMAP_PATH.exists():
        lines.append("</urlset>")

    # Если файл уже существует, дописываем в конец файла перед </urlset>
    if SITEMAP_PATH.exists():
        content = SITEMAP_PATH.read_text(encoding="utf-8")
        content = content.replace("</urlset>", "\n" + "\n".join(lines) + "\n</urlset>")
        SITEMAP_PATH.write_text(content, encoding="utf-8")
    else:
        SITEMAP_PATH.write_text("\n".join(lines), encoding="utf-8")

    logger.info(f"Sitemap обновлён с новым постом: {new_slug}")




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

    # Обновляем sitemap
    await update_sitemap(post.slug)

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