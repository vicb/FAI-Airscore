# -*- coding: utf-8 -*-
"""Public forms."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, IntegerField, SelectField, SubmitField
from airscore.user.models import User
from wtforms.validators import DataRequired, Length, Email, EqualTo


class LoginForm(FlaskForm):
    """Login form."""

    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(LoginForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self):
        """Validate the form."""
        from Defines import ADMIN_DB
        initial_validation = super(LoginForm, self).validate()
        if not initial_validation:
            return False

        '''get correct user'''

        self.user = User.query.filter_by(username=self.username.data).first()
        if not self.user:
            self.username.errors.append("Unknown username")
            return False

        if not ADMIN_DB:
            return self.validate_external()

        if not self.user.check_password(self.password.data):
            self.password.errors.append("Invalid password")
            return False

        if not self.user.active:
            self.username.errors.append("User not activated")
            return False
        return True

    def validate_external(self):
        """Validate the form."""
        import requests
        from Defines import ADMIN_AUTH_URL, ADMIN_AUTH_TYPE

        if ADMIN_AUTH_TYPE.lower() == 'rest':
            headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
            r = requests.get(ADMIN_AUTH_URL, auth=(self.username.data, self.password.data), headers=headers).json()
        else:  # implement different external auth types
            r = {'id': None}
        if not r['id'] == self.user.id:
            self.username.errors.append("Invalid password")
            return False
        return True


class ModifyParticipantForm(FlaskForm):
    id_num = IntegerField('ID')
    nat = StringField('Nat', validators=[Length(3)])
    glider = StringField('Glider')
    sponsor = StringField('Sponsor')
    certification = StringField('Certification')


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Request Password Reset')
