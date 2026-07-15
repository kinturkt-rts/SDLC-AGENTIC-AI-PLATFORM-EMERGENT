"""ORM model package — import all models here so Base.metadata is populated."""
from app.models.faq_collection import FaqCollection  # noqa: F401
from app.models.faq_chunk import FaqChunk  # noqa: F401
from app.models.question_log import QuestionLog  # noqa: F401
