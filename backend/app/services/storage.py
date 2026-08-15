from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile, HTTPException
from PIL import Image
from app.core.config import settings

ALLOWED={"image/jpeg":".jpg","image/png":".png"}
async def save_upload(inspection_id:str, image_type:str, file:UploadFile):
    if file.content_type not in ALLOWED: raise HTTPException(422,"Only JPEG and PNG image uploads are supported")
    data=await file.read()
    if not data or len(data)>settings.max_upload_bytes: raise HTTPException(422,"Image is empty or exceeds the upload limit")
    folder=settings.storage_root/"inspections"/inspection_id/image_type.lower(); folder.mkdir(parents=True,exist_ok=True)
    path=folder/(str(uuid4())+ALLOWED[file.content_type]); path.write_bytes(data)
    try:
        with Image.open(path) as image: image.verify()
        with Image.open(path) as image: width,height=image.size
    except Exception:
        path.unlink(missing_ok=True); raise HTTPException(422,"Uploaded file is not a valid image")
    return path,width,height,{"original_filename":file.filename,"content_type":file.content_type,"bytes":len(data)}
