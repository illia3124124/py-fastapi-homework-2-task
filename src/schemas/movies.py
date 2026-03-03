from datetime import date as dt_date, timedelta

from pydantic.fields import Field
from pydantic import BaseModel, field_validator


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: dt_date
    score: float
    overview: str


class MovieListResponseSchema(BaseModel):
    movies: list[MovieListItemSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int


class MovieCreateSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: dt_date = Field(...)
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: str = Field(..., pattern="^(Released|Post Production|In Production)$")
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str = Field(..., pattern="^[A-Z]{2}$")
    genres: list[str]
    actors: list[str]
    languages: list[str]

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: dt_date) -> dt_date:
        if v > dt_date.today() + timedelta(days=365):
            raise ValueError("date cannot be more than 365 days in the future")
        return v


class CountrySchema(BaseModel):
    id: int
    code: str
    name: str | None


class GenreSchema(BaseModel):
    id: int
    name: str


class ActorSchema(BaseModel):
    id: int
    name: str


class LanguageSchema(BaseModel):
    id: int
    name: str


class MovieDetailSchema(MovieCreateSchema):
    id: int
    country: CountrySchema
    genres: list[GenreSchema]
    actors: list[ActorSchema]
    languages: list[LanguageSchema]


class MovieUpdateSchema(BaseModel):
    name: str | None = Field(None, max_length=255)
    date: dt_date | None = Field(None)
    score: float | None = Field(None, ge=0, le=100)
    overview: str | None = None
    status: str | None = Field(
        None, pattern="^(Released|Post Production|In Production)$"
    )
    budget: float | None = Field(None, ge=0)
    revenue: float | None = Field(None, ge=0)
