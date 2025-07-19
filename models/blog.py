from database import db
from pydantic import BaseModel
from typing import List, Union, Dict, Optional

blog_posts_collection = db["blog_posts"]

class BlogPost(BaseModel):
    title: str
    description: str
    content: str
    author: str
    date: str
    image_link: str
    annotations: List[Union[str, Dict[str, str]]]
    slug: Optional[str] = None