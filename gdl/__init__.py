"""Read, render and author Extron GUI Designer .gdl files.

Submodules are loaded lazily so that `python -m gdl.container` does not
re-import a module the package has already pulled in.
"""
__all__ = ['open_gdl', 'open_payload', 'pack', 'payload_name']


def __getattr__(name):
    if name in __all__:
        from . import container
        return getattr(container, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
