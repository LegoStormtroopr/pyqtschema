from abc import ABC, abstractmethod
from functools import lru_cache
from json import load as load_json
from platform import system

import requests
from uritools import uricompose, urisplit, urijoin


class ResourceLoader(ABC):
    """Abstract base class for a resource loader, which accepts a URI and returns a JSON object"""

    @abstractmethod
    def load_resource(self, uri: str) -> dict:
        """Return JSON object associated with URI
        
        :param uri: URI string
        """
        pass


class HTTPResourceLoader(ResourceLoader):
    """ResourceLoader corresponding to a remote JSON file served over http."""

    def load_resource(self, uri: str) -> dict:
        return requests.get(uri).json()


class FileResourceLoader(ResourceLoader):
    """ResourceLoader corresponding to a local JSON file."""

    def load_resource(self, uri: str) -> dict:
        result = urisplit(uri)

        if result.authority:
            raise ValueError("Network paths unsupported")

        path = result.path

        # File URIs either include the authority component, or an additional forward slash (which we strip from path)
        if system() == 'Windows':
            path = path[1:]

        with open(path) as f:
            return load_json(f)


class DocumentLoader(ResourceLoader):
    """ResourceLoader corresponding to schema document.
    
    Used to facilitate internal references when references are not resolved with base uri 
    """

    def __init__(self, document: dict, location: str):
        self.location = location
        self.document = document

    def load_resource(self, uri: str) -> dict:
        if uri != self.location:
            raise ValueError("Cannot retrieve external documents")
        return self.document


class URILoaderRegistry:
    """Registry to load a URI according to URI scheme"""

    def __init__(self):
        self.scheme_to_loader = {}

    def load_resource_from_loader(self, loader: ResourceLoader, uri: str) -> dict:
        """Return JSON object returned by loader for given URI
        
        :param loader: ResourceLoader object
        :param uri: URI string
        """
        print("Loading resource {} with {}".format(uri, loader))
        return loader.load_resource(uri)

    def load_uri(self, uri: str) -> dict:
        """Return the JSON object associated with given URI
        
        :param uri: URI string
        """
        result = urisplit(uri)

        location = uricompose(result.scheme, result.authority, result.path)
        loader = self.scheme_to_loader[result.scheme]
        resource = self.load_resource_from_loader(loader, location)

        if result.fragment:
            assert result.fragment.startswith("/")
            reference = Reference(result.fragment[1:])
            return reference.extract(resource)

        return resource

    def register_for_scheme(self, scheme: str, loader):
        self.scheme_to_loader[scheme] = loader


def create_cached_uri_loader_registry(cache_size=1024):
    """Create a cached URILoaderRegistry subclass and return it
    
    :param cache_size: size of registry cache (entries)
    """

    class CachedURILoaderRegistry(URILoaderRegistry):
        load_resource_from_loader = lru_cache(1024)(URILoaderRegistry.load_resource_from_loader)

    return CachedURILoaderRegistry


class Reference:
    def __init__(self, uri: str):
        self.elements = [e.replace('~1', '/').replace('~0', '~') for e in uri.split('/')]

    def extract(self, obj: dict):
        """Return JSON object associated with this reference URI
        
        :param obj: dict-like JSON object
        """
        for elem in self.elements:
            obj = obj[elem]
        return obj


class Context:
    """Object describing JSON scope context for dereferencing '$ref' references whilst respecting 'id' fields"""

    def __init__(self, scope_uri: str, registry: URILoaderRegistry):
        self.scope_uri = scope_uri
        self.registry = registry

    def follow_uri(self, uri: str) -> 'Context':
        """Return new Context corresponding to scope after following uri
        
        :param uri: URI string
        """
        new_uri = urijoin(self.scope_uri, uri)
        return self.__class__(new_uri, self.registry)

    def dereference(self, uri: str) -> dict:
        """Return JSON object corresponding to resolved URI reference
        
        :param uri: URI string
        """
        reference_path = urijoin(self.scope_uri, uri)
        return self.registry.load_uri(reference_path)

    def __repr__(self):
        return "Context({!r}, {!r})".format(self.scope_uri, self.registry)
