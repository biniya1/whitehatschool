from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, SelectField
from wtforms.validators import (
    DataRequired, Length, Regexp, EqualTo, NumberRange, Optional, ValidationError,
)

USERNAME_RE = r"^[A-Za-z0-9_]+$"
# At least one letter and one digit; length is enforced separately so this
# regex just checks composition.
PASSWORD_COMPLEXITY_RE = r"^(?=.*[A-Za-z])(?=.*\d).+$"


class RegisterForm(FlaskForm):
    username = StringField("사용자명", validators=[
        DataRequired(message="사용자명을 입력해주세요."),
        Length(min=3, max=20, message="사용자명은 3~20자여야 합니다."),
        Regexp(USERNAME_RE, message="사용자명은 영문, 숫자, 밑줄(_)만 사용할 수 있습니다."),
    ])
    password = PasswordField("비밀번호", validators=[
        DataRequired(message="비밀번호를 입력해주세요."),
        Length(min=8, max=128, message="비밀번호는 8자 이상이어야 합니다."),
        Regexp(PASSWORD_COMPLEXITY_RE, message="비밀번호는 영문과 숫자를 모두 포함해야 합니다."),
    ])
    confirm_password = PasswordField("비밀번호 확인", validators=[
        DataRequired(message="비밀번호 확인을 입력해주세요."),
        EqualTo("password", message="비밀번호가 일치하지 않습니다."),
    ])


class LoginForm(FlaskForm):
    username = StringField("사용자명", validators=[DataRequired(), Length(max=30)])
    password = PasswordField("비밀번호", validators=[DataRequired(), Length(max=128)])


class ProfileForm(FlaskForm):
    bio = TextAreaField("소개글", validators=[Optional(), Length(max=500)])
    current_password = PasswordField("현재 비밀번호", validators=[Optional(), Length(max=128)])
    new_password = PasswordField("새 비밀번호", validators=[
        Optional(),
        Length(min=8, max=128, message="비밀번호는 8자 이상이어야 합니다."),
        Regexp(PASSWORD_COMPLEXITY_RE, message="비밀번호는 영문과 숫자를 모두 포함해야 합니다."),
    ])
    confirm_new_password = PasswordField("새 비밀번호 확인", validators=[
        Optional(),
        EqualTo("new_password", message="새 비밀번호가 일치하지 않습니다."),
    ])

    def validate_new_password(self, field):
        if field.data and not self.current_password.data:
            raise ValidationError("비밀번호를 변경하려면 현재 비밀번호를 입력해야 합니다.")


class ProductForm(FlaskForm):
    title = StringField("상품명", validators=[
        DataRequired(message="상품명을 입력해주세요."), Length(max=100),
    ])
    description = TextAreaField("상품 설명", validators=[
        DataRequired(message="상품 설명을 입력해주세요."), Length(max=2000),
    ])
    price = IntegerField("가격", validators=[
        DataRequired(message="가격을 입력해주세요."),
        NumberRange(min=0, max=1_000_000_000, message="가격은 0 이상, 10억 이하의 숫자여야 합니다."),
    ])
    image = FileField("상품 사진", validators=[
        FileAllowed(["png", "jpg", "jpeg", "gif", "webp"], "이미지 파일만 업로드할 수 있습니다."),
    ])


class ReportForm(FlaskForm):
    target_type = SelectField("신고 대상 유형", choices=[
        ("product", "상품"), ("user", "사용자"),
    ], validators=[DataRequired()])
    target_id = StringField("신고 대상 ID", validators=[DataRequired(), Length(max=36)])
    reason = TextAreaField("신고 사유", validators=[
        DataRequired(message="신고 사유를 입력해주세요."), Length(min=5, max=500),
    ])


class TransferForm(FlaskForm):
    target_username = StringField("받는 사람 사용자명", validators=[
        DataRequired(message="받는 사람을 입력해주세요."), Length(max=30),
    ])
    amount = IntegerField("금액", validators=[
        DataRequired(message="금액을 입력해주세요."),
        NumberRange(min=1, max=1_000_000_000, message="금액은 1 이상이어야 합니다."),
    ])


class SearchForm(FlaskForm):
    class Meta:
        csrf = False

    q = StringField("검색어", validators=[Optional(), Length(max=100)])
