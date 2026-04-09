import logging

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from jinja2_logging_ext import LoggingExtension

logging.basicConfig(format="%(levelname)s %(name)s %(message)s")
logging.getLogger("jinja2.lifecycle").setLevel(logging.DEBUG)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.jinja_env.add_extension(LoggingExtension)
app.jinja_env.banned_words = {"secret", "password", "admin"}
class Base(DeclarativeBase):
  pass
db = SQLAlchemy(app, model_class=Base)


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    config = db.Column(db.JSON, nullable=False, default=dict)

    def to_dict(self):
        return {"id": self.id, "config": self.config}


created = False
@app.before_request
def before_request():
    global created
    if not created:
        print("Creating tables...")
        with app.app_context():
            db.create_all()
            print("Tables created.")
        created = True


@app.route("/items", methods=["GET"])
def list_items():
    items = Item.query.all()
    return jsonify([item.to_dict() for item in items])


@app.route("/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    item = db.get_or_404(Item, item_id)
    return jsonify(item.to_dict())


@app.route("/items/html", methods=["GET"])
def list_items_html():
    items = Item.query.all()
    return render_template("items.jinja2", items=items)


@app.route("/items/<int:item_id>/html", methods=["GET"])
def get_item_html(item_id):
    item = db.get_or_404(Item, item_id)
    return render_template("item.jinja2", item=item)


@app.route("/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    item = Item(config=data)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    item = db.get_or_404(Item, item_id)
    data = request.get_json(silent=True) or {}
    item.config = data
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)
    db.session.delete(item)
    db.session.commit()
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
