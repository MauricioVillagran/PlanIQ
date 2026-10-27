"""Paginación común: `page` (desde 1), `page_size` y `total`."""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


class PageParams(BaseModel):
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def _page_params(
    page: Annotated[int, Query(ge=1, description="Página, desde 1")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Registros por página (máx. {MAX_PAGE_SIZE})")
    ] = DEFAULT_PAGE_SIZE,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageParamsDep = Annotated[PageParams, Depends(_page_params)]


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int

    @classmethod
    def build(cls, items: list[T], params: PageParams, total: int) -> "Page[T]":
        return cls(items=items, page=params.page, page_size=params.page_size, total=total)
