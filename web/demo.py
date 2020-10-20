
import flask
import mimetypes
import pkgutil

def serve(pkg, file):
  try:
    data = pkgutil.get_data(pkg, file)
    if data is None:
      return 'File not found', 404
    print(mimetypes.guess_type(file))
    return data, 200, {'Content-Type': mimetypes.guess_type(file)[0]}
  except Exception as e:
    print(e)
    return 'File not found', 404


def root_serve(file):
  print(file)
  return serve('impulse.web', file)

def fake_json():
  return '{"glossary":{"title":"example glossary","GlossDiv":{"title":"S","GlossList":{"GlossEntry":{"ID":"SGML","SortAs":"SGML","GlossTerm":"Standard Generalized Markup Language","Acronym":"SGML","Abbrev":"ISO 8879:1986","GlossDef":{"para":"A meta-markup language, used to create markup languages such as DocBook.","GlossSeeAlso":["GML","XML"]},"GlossSee":"markup"}}}}}'

def main():
  flask_app = flask.Flask(__name__)
  flask_app.route('/<file>')(root_serve)
  flask_app.route('/foo')(fake_json)
  flask_app.run(host='0.0.0.0', port=1234)