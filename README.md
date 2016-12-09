wsgi application with route decorator
=====================================

In 175 lines of code, with no external dependencies

Example usage
``` python
from wsgi import App


app = App()

@app.route('/')
def home(r):
    # do something with headers
    print(r.headers)

    # do something with query
    print(r.query)

    return 'Welcome home', {'custom_headers': 'header_be_here'}
    

@app.route('/form', methods=['POST'])
def form(r):
    # do something with form data and files dictionary
    print(r.data)

    return 'submitted successfully'

if __name__ == '__main__':
    app.run()

```
