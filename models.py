from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    reward = db.Column(db.Integer, default=0)

class Language(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Sentence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    english_text = db.Column(db.String(200), nullable=False)

class Translation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sentence_id = db.Column(db.Integer, db.ForeignKey('sentence.id'))
    language_id = db.Column(db.Integer, db.ForeignKey('language.id'))
    mumuye_translation = db.Column(db.String(200))
    status = db.Column(db.String(20), default="pending")
    feedback = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='translations')
    sentence = db.relationship('Sentence', backref='translations')
    language = db.relationship('Language', backref='translations')
