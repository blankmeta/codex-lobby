"""Explicit HTTP proxy requests, independent of curl and host proxy variables."""
import http.client
import ssl
from urllib.parse import urlsplit


def proxy_get(proxy, url, *, timeout=10):
    endpoint, target = urlsplit(proxy), urlsplit(url)
    if target.scheme == "https":
        connection = http.client.HTTPSConnection(endpoint.hostname, endpoint.port, timeout=timeout,
                                                context=ssl.create_default_context())
        connection.set_tunnel(target.hostname, target.port or 443)
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
    else:
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=timeout)
        path = url
    try:
        connection.request("GET", path, headers={"Host": target.netloc})
        response = connection.getresponse()
        return response.status, response.read(65536)
    finally:
        connection.close()
