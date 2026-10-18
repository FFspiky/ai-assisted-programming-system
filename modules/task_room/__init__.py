"""AI task room. Models must be loaded before the host calls db.create_all()."""


def register_task_room(app):
    from .routes import blueprint

    app.register_blueprint(blueprint)
