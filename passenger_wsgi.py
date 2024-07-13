from flask import Flask
from app import app as application

if __name__ == '__main__':
    application.run(host='10.214.203.211', port=5000)
