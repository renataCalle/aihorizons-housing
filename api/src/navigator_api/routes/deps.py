from typing import Annotated

from fastapi import Depends, Request

from navigator_api.sources.base import SiteSource


def get_source(request: Request) -> SiteSource:
    return request.app.state.source


Source = Annotated[SiteSource, Depends(get_source)]
