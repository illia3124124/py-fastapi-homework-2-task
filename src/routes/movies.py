from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import ValidationError

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    GenreSchema,
    ActorSchema,
    CountrySchema,
    LanguageSchema,
    MovieUpdateSchema,
)

router = APIRouter()


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    try:
        total_items_query = await db.execute(
            select(func.count()).select_from(MovieModel)
        )
        total_items = total_items_query.scalar_one()

        total_pages = (total_items + per_page - 1) // per_page
        if (page > total_pages and total_pages != 0) or total_items == 0:
            raise HTTPException(status_code=404, detail="No movies found.")

        offset = (page - 1) * per_page
        movies_query = await db.execute(
            select(MovieModel)
            .offset(offset)
            .limit(per_page)
            .order_by(MovieModel.id.desc())
        )
        movies = movies_query.scalars().all()
        movies = [
            MovieListItemSchema(
                id=movie.id,
                name=movie.name,
                date=movie.date,
                score=movie.score,
                overview=movie.overview,
            )
            for movie in movies
        ]

        prev_page = (
            f"/theater/movies/?page={page - 1}&per_page={per_page}"
            if page > 1
            else None
        )
        next_page = (
            f"/theater/movies/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        )

        return MovieListResponseSchema(
            movies=movies,
            prev_page=prev_page,
            next_page=next_page,
            total_pages=total_pages,
            total_items=total_items,
        )
    except IntegrityError:
        raise HTTPException(status_code=500, detail="Database integrity error")


@router.post("/movies/", response_model=MovieDetailSchema, status_code=201)
async def create_movie(
    movie_data: MovieCreateSchema, db: AsyncSession = Depends(get_db)
):
    country_query = await db.execute(
        select(CountryModel).where(CountryModel.code == movie_data.country)
    )
    country = country_query.scalar_one_or_none()
    if not country:
        country = CountryModel(code=movie_data.country)
        db.add(country)

    genres_query = await db.execute(
        select(GenreModel).where(GenreModel.name.in_(movie_data.genres))
    )
    actors_query = await db.execute(
        select(ActorModel).where(ActorModel.name.in_(movie_data.actors))
    )
    languages_query = await db.execute(
        select(LanguageModel).where(LanguageModel.name.in_(movie_data.languages))
    )
    genres = genres_query.scalars().all()
    actors = actors_query.scalars().all()
    languages = languages_query.scalars().all()

    genres_to_create = set(movie_data.genres) - {genre.name for genre in genres}
    actors_to_create = set(movie_data.actors) - {actor.name for actor in actors}
    languages_to_create = set(movie_data.languages) - {
        language.name for language in languages
    }

    for genre_name in genres_to_create:
        genre = GenreModel(name=genre_name)
        db.add(genre)
        genres.append(genre)

    for actor_name in actors_to_create:
        actor = ActorModel(name=actor_name)
        db.add(actor)
        actors.append(actor)

    for language_name in languages_to_create:
        language = LanguageModel(name=language_name)
        db.add(language)
        languages.append(language)

    movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )
    db.add(movie)
    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists.",
        )

    return MovieDetailSchema(
        id=movie.id,
        name=movie.name,
        date=movie.date,
        score=movie.score,
        overview=movie.overview,
        status=movie.status,
        budget=movie.budget,
        revenue=movie.revenue,
        country=CountrySchema(id=country.id, code=country.code, name=country.name),
        genres=[GenreSchema(id=genre.id, name=genre.name) for genre in genres],
        actors=[ActorSchema(id=actor.id, name=actor.name) for actor in actors],
        languages=[
            LanguageSchema(id=language.id, name=language.name) for language in languages
        ],
    )


@router.get("/movies/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie_detail(movie_id: int, db: AsyncSession = Depends(get_db)):
    try:
        movie_query = await db.execute(
            select(MovieModel)
            .options(
                selectinload(MovieModel.country),
                selectinload(MovieModel.genres),
                selectinload(MovieModel.actors),
                selectinload(MovieModel.languages),
            )
            .where(MovieModel.id == movie_id)
        )
    except DBAPIError:
        raise HTTPException(status_code=400, detail="Invalid movie ID")

    movie = movie_query.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema(
        id=movie.id,
        name=movie.name,
        date=movie.date,
        score=movie.score,
        overview=movie.overview,
        status=movie.status,
        budget=movie.budget,
        revenue=movie.revenue,
        country=CountrySchema(
            id=movie.country.id, code=movie.country.code, name=movie.country.name
        ),
        genres=[GenreSchema(id=genre.id, name=genre.name) for genre in movie.genres],
        actors=[ActorSchema(id=actor.id, name=actor.name) for actor in movie.actors],
        languages=[
            LanguageSchema(id=language.id, name=language.name)
            for language in movie.languages
        ],
    )


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    try:
        movie_query = await db.execute(
            select(MovieModel).where(MovieModel.id == movie_id)
        )
    except DBAPIError:
        raise HTTPException(status_code=400, detail="Invalid movie ID")

    movie = movie_query.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()


@router.patch("/movies/{movie_id}/", response_model=dict)
async def update_movie(
    movie_id: int,
    movie_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        validated_data = MovieUpdateSchema.model_validate(movie_data)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    if all(value is None for value in validated_data.model_dump().values()):
        raise HTTPException(status_code=400, detail="Invalid input data.")

    try:
        movie_query = await db.execute(
            select(MovieModel).where(MovieModel.id == movie_id)
        )
    except DBAPIError:
        raise HTTPException(status_code=400, detail="Invalid movie ID")

    movie = movie_query.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    for field, value in validated_data.model_dump().items():
        if value is not None:
            setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists.",
        )

    return {"detail": "Movie updated successfully."}
