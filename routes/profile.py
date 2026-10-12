import io
import re
import warnings

from flask import Blueprint, request, send_file, session
from flask_login import current_user, login_required, logout_user
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError

from models import User, db
from routes.api_response import api_error, api_success
from routes.guards import rate_limit
from services.profile_service import practice_stats, user_payload

profile_blueprint = Blueprint("profile", __name__)


@profile_blueprint.get("/profile")
@login_required
def get_profile():
    return api_success({"user": user_payload(current_user), "stats": practice_stats(current_user)})


@profile_blueprint.patch("/profile")
@login_required
@rate_limit(max_calls=20, window_seconds=60)
def update_profile():
    data = request.get_json(silent=True) or {}
    values = {}
    for field, maximum in [
        ("username", 80),
        ("email", 120),
        ("display_name", 80),
        ("bio", 160),
        ("location", 80),
    ]:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or len(value.strip()) > maximum:
            return api_error("INVALID_FIELD", f"{field}格式不正确或超过长度限制", 400)
        values[field] = value.strip()
    username = values.get("username", current_user.username)
    email = values.get("email", current_user.email)
    if len(username) < 3 or any(ord(c) < 32 for c in username):
        return api_error(
            "INVALID_USERNAME", "用户名长度应为 3-80 个字符，不能包含换行或控制字符", 400
        )
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return api_error("INVALID_EMAIL", "邮箱格式不正确", 400)
    if email != current_user.email:
        password = data.get("current_password", "")
        if (
            not isinstance(password, str)
            or len(password) > 1024
            or not current_user.check_password(password)
        ):
            return api_error("PASSWORD_REQUIRED", "修改邮箱需要输入正确的当前密码", 400)
    other = User.query.filter(User.id != current_user.id)
    if other.filter_by(username=username).first():
        return api_error("USERNAME_EXISTS", "用户名已存在，请换一个", 409)
    if other.filter_by(email=email).first():
        return api_error("EMAIL_EXISTS", "邮箱已被使用", 409)
    for field, value in values.items():
        setattr(current_user, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_error("PROFILE_CONFLICT", "用户名或邮箱已被使用", 409)
    return api_success({"user": user_payload(current_user)}, message="资料已保存")


@profile_blueprint.post("/profile/password")
@login_required
@rate_limit(max_calls=5, window_seconds=60)
def change_password():
    data = request.get_json(silent=True) or {}
    old, new = data.get("current_password", ""), data.get("new_password", "")
    if (
        not isinstance(old, str)
        or not isinstance(new, str)
        or not 8 <= len(new) <= 128
        or len(old) > 1024
    ):
        return api_error("INVALID_PASSWORD", "新密码长度应为 8-128 个字符", 400)
    if not current_user.check_password(old):
        return api_error("INVALID_PASSWORD", "当前密码不正确", 400)
    if old == new:
        return api_error("INVALID_PASSWORD", "新密码不能与当前密码相同", 400)
    current_user.set_password(new)
    current_user.auth_version += 1
    db.session.commit()
    logout_user()
    session.clear()
    return api_success(message="密码已修改，请使用新密码重新登录")


@profile_blueprint.get("/profile/avatar")
@login_required
def avatar_image():
    if not current_user.avatar_image:
        return api_error("AVATAR_MISSING", "尚未上传头像", 404)
    response = send_file(io.BytesIO(current_user.avatar_image), mimetype="image/png")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@profile_blueprint.post("/profile/avatar")
@login_required
@rate_limit(max_calls=10, window_seconds=60)
def upload_avatar():
    request.max_content_length = 3 * 1024 * 1024
    upload = request.files.get("avatar")
    if not upload:
        return api_error("AVATAR_MISSING", "请选择头像图片", 400)
    raw = upload.stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return api_error("AVATAR_TOO_LARGE", "头像不能超过 2 MB", 400)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=["PNG", "JPEG", "WEBP"]) as source:
                if source.width * source.height > 16_000_000:
                    return api_error("AVATAR_TOO_LARGE", "头像尺寸不能超过 1600 万像素", 400)
                source.load()
                avatar = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGBA"), (256, 256))
                # Re-encode pixels only, without metadata or active file content.
                clean = Image.new("RGBA", avatar.size)
                clean.paste(avatar)
                output = io.BytesIO()
                clean.save(output, format="PNG")
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return api_error("INVALID_AVATAR", "请选择有效的 PNG、JPG 或 WebP 图片", 400)
    current_user.avatar_image = output.getvalue()
    db.session.commit()
    return api_success({"user": user_payload(current_user)}, message="头像已更新")


@profile_blueprint.delete("/profile/avatar")
@login_required
def remove_avatar():
    current_user.avatar_image = None
    db.session.commit()
    return api_success({"user": user_payload(current_user)}, message="已恢复默认头像")
