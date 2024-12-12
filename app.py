from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, DateField, SelectField
from wtforms.validators import InputRequired, Length, EqualTo, NumberRange
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# 設置資料庫配置
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accounting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
Bootstrap(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    item = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric, nullable=False)

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=100)])
    submit = SubmitField('Login')

class RecordForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[InputRequired()])
    item = StringField('Item', validators=[InputRequired(), Length(max=100)])
    amount = DecimalField('Amount', validators=[InputRequired(), NumberRange(min=-9999999999, max=9999999999)])
    submit = SubmitField('Add Record')

class FilterForm(FlaskForm):
    month = SelectField('Month', choices=[('all', 'All')] + [(str(i), str(i)) for i in range(1, 13)])
    year = SelectField('Year', choices=[('all', 'All')] + [(str(i), str(i)) for i in range(2000, 2026)])
    filter_type = SelectField('Filter', choices=[('default', 'Default'), ('date_asc', 'Date Ascending'), ('amount_desc', 'Amount Descending'), ('amount_asc', 'Amount Ascending')])
    submit = SubmitField('Filter')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        password = generate_password_hash(form.password.data)
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different one.')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!')
            return redirect(url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = RecordForm()
    filter_form = FilterForm()

    query = Record.query.filter_by(user_id=session['user_id'])

    if form.validate_on_submit():
        date = form.date.data
        item = form.item.data
        amount = form.amount.data
        user_id = session['user_id']
        new_record = Record(user_id=user_id, date=date, item=item, amount=amount)
        db.session.add(new_record)
        db.session.commit()
        flash('Record added successfully!')
        return redirect(url_for('index'))

    if filter_form.validate_on_submit():
        month = filter_form.month.data
        year = filter_form.year.data
        filter_type = filter_form.filter_type.data

        if month != 'all':
            query = query.filter(db.extract('month', Record.date) == int(month))
        if year != 'all':
            query = query.filter(db.extract('year', Record.date) == int(year))

        if filter_type == 'date_asc':
            query = query.order_by(Record.date.asc())
        elif filter_type == 'amount_desc':
            query = query.order_by(Record.amount.desc())
        elif filter_type == 'amount_asc':
            query = query.order_by(Record.amount.asc())
        else:
            query = query.order_by(Record.date.desc())

    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    records = pagination.items

    return render_template('index.html', form=form, filter_form=filter_form, records=records, pagination=pagination)

@app.route('/show_all_records', methods=['GET', 'POST'])
@login_required
def show_all_records():
    query = Record.query.filter_by(user_id=session['user_id']).order_by(Record.date.desc())
    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    records = pagination.items
    form = RecordForm()
    filter_form = FilterForm()
    return render_template('index.html', form=form, filter_form=filter_form, records=records, pagination=pagination)




@app.route('/delete/<int:record_id>')
@login_required
def delete(record_id):
    record = Record.query.get_or_404(record_id)
    if record.user_id != session['user_id']:
        flash('You are not authorized to delete this record.')
        return redirect(url_for('index'))
    db.session.delete(record)
    db.session.commit()
    flash('Record deleted successfully!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 創建資料庫和表格
    app.run(debug=True)
