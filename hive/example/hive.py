# Hive.py is a service which loads docker images

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

if __name__ == '__main__':
  main()

def main():
  print('running on 0.0.0.0:8899')
  app.run(host="0.0.0.0", port=8899)