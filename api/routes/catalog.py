from fastapi import APIRouter

from services.catalog import APP_TEMPLATES, IMAGE_CATALOG

router = APIRouter()


@router.get("")
def get_catalog():
    return {
        "apps": APP_TEMPLATES,
        "images": IMAGE_CATALOG,
    }
