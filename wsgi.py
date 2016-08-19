# wsgi.py


from cgi import FieldStorage, MiniFieldStorage
from collections import defaultdict
from functools import update_wrapper, wraps
from wsgiref.simple_server import make_server

try:
    iteritems = dict.iteritems
    import httplib
    from urlparse import parse_qsl
except (ImportError, AttributeError):  # py3
    iteritems = dict.items
    import http.client as httplib
    from urllib.parse import parse_qsl


wanted_headers = {
    'REQUEST_METHOD', 'PATH_INFO', 'REMOTE_ADDR', 'REMOTE_HOST', 'CONTENT_TYPE'
}


class lazy_property(object):
    """
    From https://github.com/faif/python-patterns/blob/master/lazy_evaluation.py
    """

    def __init__(self, function):
        self.function = function
        update_wrapper(self, function)

    def __get__(self, obj, type_):
        if obj is None:
            return self
        val = self.function(obj)
        obj.__dict__[self.function.__name__] = val
        return val


class Request(object):

    def __init__(self, environ):
        self.environ = environ
        headers = self.headers
        self.content_type = headers.get('CONTENT_TYPE', '')
        self.length = headers['CONTENT_LENGTH']
        self.method = headers['REQUEST_METHOD']
        self.path = headers['PATH_INFO']

    @lazy_property
    def query(self):
        query = self.environ.get('QUERY_STRING')
        if query:
            parsed_query = parse_qsl(query)
            qs = defaultdict(list)
            for k, v in parsed_query:
                qs[k].append(v)
            return dict(qs)

    @lazy_property
    def headers(self):
        environ = self.environ
        length = int(environ.get('CONTENT_LENGTH') or 0)

        headers = {
            'CONTENT_LENGTH': length,
        }
        headers.update(
            (k, v)
            for k, v
            in iteritems(environ)
            if k in wanted_headers or k.startswith('HTTP_')
        )
        return headers

    @lazy_property
    def data(self):
        environ = self.environ
        wsgi_input = environ['wsgi.input']

        content_type = self.content_type.lower()
        if 'form' in content_type:
            env_data = FieldStorage(wsgi_input, environ=environ)
            return {
                k.name: k.file if k.filename else k.value
                for k in env_data.list
                if not isinstance(k, MiniFieldStorage)
            }
        else:
            return wsgi_input.read(self.length)


class Response(object):
    def __init__(self, make_response, code=200, data=''):
        self.code = code
        self.make_response = make_response

        # view can return str or str and a dict of headers
        self.data, _headers = (data[0], data[1]) \
            if isinstance(data, tuple) else (data, {})

        headers = {k: v for k, v in iteritems(_headers)}
        for k in headers:
            if 'content-type' in k.lower():
                break
        else:
            headers['Content-Type'] = 'text/html'

        self.headers = headers

    def render(self):
        code = self.code
        resp_code = '{} {}'.format(code, httplib.responses[code])

        if resp_code[0] in {'4', '5'}:
            data = resp_code.encode('utf-8')
        else:
            _data = self.data
            try:
                data = bytes(_data)
            except Exception:
                data = str(_data).encode('utf-8')

        headers = self.headers
        # headers.append['Content-Length'] = len(data)
        self.make_response(resp_code, list(iteritems(headers)))
        yield data


class App(object):

    def __init__(self):
        self.routes = {}

    def route(self, url, methods=['GET']):
        routes = self.routes

        def decorate(f):

            @wraps(f)
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)

            routes[url] = {'methods': methods, 'func': wrapper}
            return wrapper

        return decorate

    def path_dispatch(self, request, make_response):
        path = request.path
        view = self.routes.get(path)

        if view:
            method = request.method
            methods = set(view['methods'])
            if method in methods:
                data = view['func'](request)
                response = Response(make_response, data=data)
            else:
                response = Response(make_response, 405)
        else:
            response = Response(make_response, 404)

        return response

    def __call__(self, environ, make_response):
        request = Request(environ)
        response = self.path_dispatch(request, make_response)
        return response.render()

    def run(self, host='', port=8080):
        httpd = make_server(host, port, self)
        print('Serving on {host}:{port}'.format(host=host, port=port))
        httpd.serve_forever()
