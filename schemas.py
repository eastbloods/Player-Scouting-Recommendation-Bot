from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class SearchPlayerRequest(BaseModel):
    text: str


class SearchPlayerResponse(BaseModel):
    text: str

