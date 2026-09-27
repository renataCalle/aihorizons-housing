from typing import Annotated

from fastapi import Depends, Request

from navigator_api.search.parse_ai import AIParser
from navigator_api.sources.base import SiteSource


def get_source(request: Request) -> SiteSource:
    return request.app.state.source


def get_ai_parser(request: Request) -> AIParser | None:
    return request.app.state.ai_parser


Source = Annotated[SiteSource, Depends(get_source)]
AI = Annotated[AIParser | None, Depends(get_ai_parser)]
