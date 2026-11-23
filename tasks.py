"""Optional Celery worker for generating small deck photos."""

import os
from io import BytesIO

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery("recipe_box", broker=os.getenv("CELERY_BROKER_URL"))
celery_app.conf.update(task_ignore_result=True, task_serializer="json", accept_content=["json"],
                       task_acks_late=True, broker_connection_timeout=3, worker_prefetch_multiplier=1)


@celery_app.task(name="recipe_box.photo_thumbnail", max_retries=3, soft_time_limit=30, time_limit=40)
def photo_thumbnail(recipe_id, filename, owner_id=None):
    from botocore.exceptions import BotoCoreError, ClientError
    from flask import g
    from PIL import Image, ImageOps, UnidentifiedImageError
    from app import MAX_FILE_SIZE, S3_BUCKET, S3_ENDPOINT, app, read_stored_photo, storage_client, storage_key, thumbnail_name
    from model import Recipe, db

    if not S3_ENDPOINT:
        return
    with app.app_context():
        g.recipe_user_id = owner_id
        photo_owner = db.session.query(Recipe.id).filter_by(id=recipe_id, image_filename=filename, owner_id=owner_id)
        if photo_owner.first() is None:
            return
        db.session.rollback()
        try:
            photo = read_stored_photo(filename)
            if not photo or len(photo) > MAX_FILE_SIZE:
                return
            with Image.open(BytesIO(photo)) as source:
                if source.width * source.height > 22_000_000:
                    return
                picture = ImageOps.exif_transpose(source)
                picture.thumbnail((640, 420))
                with BytesIO() as output:
                    picture.save(output, format="WEBP", quality=80)
                    data = output.getvalue()
            storage_client().put_object(Bucket=S3_BUCKET, Key=storage_key(thumbnail_name(filename)),
                                        Body=data, ContentType="image/webp")
            if photo_owner.first() is None:
                storage_client().delete_object(Bucket=S3_BUCKET, Key=storage_key(thumbnail_name(filename)))
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
            return
        except (ClientError, BotoCoreError) as error:
            # A temporary storage failure should not discard a queued photo.
            raise photo_thumbnail.retry(exc=RuntimeError(type(error).__name__), countdown=30) from None
