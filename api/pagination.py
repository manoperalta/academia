"""Paginacao com teto de itens por pagina (RNF-033)."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class PaginacaoPadrao(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
