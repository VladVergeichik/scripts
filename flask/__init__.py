# coding: utf-8
import os
import shopify
import sys
import csv
import logging
import re


sys.path.append('libs')
import xlrd
import xlwt
from flask import Flask, render_template, send_from_directory, request, send_file, flash, request, redirect, url_for, Blueprint
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask.cli import main

db = SQLAlchemy()


def create_app():
    UPLOAD_FOLDER = 'upload'

    app = Flask(__name__)
    # app.config['DEBUG'] = True
    app.config['SECRET_KEY'] = 'partzstopmicro'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    app.wsgi_app = ProxyFix(app.wsgi_app)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from auth import auth as auth_blueprint
    from basic import basic as app_blueprint
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(app_blueprint)
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port='8015')
