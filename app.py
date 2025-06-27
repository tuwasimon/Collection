from flask import Flask, render_template, request, redirect, flash, abort, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import csv
from datetime import datetime
from flask import url_for

from models import db, User, Sentence, Translation, Language

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def seed_languages():
    if Language.query.count() == 0:
        langs = ["Mumuye", "Jukun", "Tiv", "Hausa", "Fulfulde", "Igbo", "Yoruba", "Kanuri"]
        for name in langs:
            db.session.add(Language(name=name))
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'])
        user = User(username=request.form['username'], phone=request.form['phone'], password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!')
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(phone=request.form['phone']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/dashboard')
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = User.query.filter_by(phone=request.form['phone']).first()
        if user and check_password_hash(user.password, request.form['password']) and user.is_admin:
            login_user(user)
            return redirect('/admin')
        flash('Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        user = User.query.filter_by(phone=request.form['phone']).first()
        if user and check_password_hash(user.password, request.form['password']) and not user.is_admin:
            login_user(user)
            return redirect('/dashboard')
        flash('Invalid user credentials')
    return render_template('user_login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    languages = Language.query.all()
    selected_language_id = request.args.get('language_id')
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of sentences per page

    selected_language = None
    if selected_language_id:
        selected_language = Language.query.get(int(selected_language_id))

    sentences_pagination = Sentence.query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'dashboard.html',
        sentences=sentences_pagination.items,
        languages=languages,
        selected_language=selected_language,
        pagination=sentences_pagination,
        selected_language_id=selected_language_id
    )

@app.route('/submit', methods=['POST'])
@login_required
def submit_translation():
    translation = Translation(
        user_id=current_user.id,
        sentence_id=request.form['sentence_id'],
        language_id=request.form['language_id'],
        mumuye_translation=request.form['mumuye_translation']
    )
    db.session.add(translation)
    db.session.commit()
    flash('Translation submitted!')
    return redirect('/dashboard')

@app.route('/submit_translations', methods=['POST'])
@login_required
def submit_translations():
    language_id = request.form['language_id']
    sentence_ids = [int(sid) for sid in request.form.getlist('sentence_ids')]
    for sentence_id in sentence_ids:
        translation_text = request.form.get(f'translations_{sentence_id}')
        if translation_text:
            translation = Translation(
                user_id=current_user.id,
                sentence_id=sentence_id,
                language_id=language_id,
                mumuye_translation=translation_text
            )
            db.session.add(translation)
    db.session.commit()
    flash('Translations submitted!')
    return redirect('/dashboard')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    users = User.query.all()
    return render_template("admin.html", users=users)

@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    language_id = request.args.get('language_id')
    query = Translation.query.filter_by(user_id=user_id)
    if language_id:
        query = query.filter(Translation.language_id == int(language_id))
    if start_date:
        query = query.filter(Translation.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(Translation.created_at <= datetime.strptime(end_date, "%Y-%m-%d"))
    translations = query.all()
    languages = Language.query.all()
    return render_template(
        "admin_user_detail.html",
        user=user,
        translations=translations,
        start_date=start_date,
        end_date=end_date,
        languages=languages,
        selected_language_id=language_id
    )

@app.route('/review/<int:translation_id>/<action>')
@login_required
def review_translation(translation_id, action):
    if not current_user.is_admin:
        abort(403)
    translation = Translation.query.get(translation_id)
    if action == "approve":
        translation.status = "approved"
        translation.feedback = "Well done!"
        translation.user.reward += 20
    elif action == "reject":
        translation.status = "rejected"
        translation.feedback = "Please review the translation."
    db.session.commit()
    return redirect('/admin')

@app.route('/download_translations')
@login_required
def download_translations():
    if not current_user.is_admin:
        abort(403)
    translations = Translation.query.order_by(Translation.user_id, Translation.language_id, Translation.sentence_id).all()
    def generate():
        data = [
            ['English', 'Translation']
        ]
        for t in translations:
            if not t.sentence or not t.mumuye_translation:
                continue  # Skip broken records
            data.append([
                t.sentence.english_text,
                t.mumuye_translation
            ])
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        return output.getvalue()
    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=translations.csv"}
    )

@app.route('/admin/delete_translation/<int:translation_id>/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_translation(translation_id, user_id):
    if not current_user.is_admin:
        abort(403)
    translation = Translation.query.get(translation_id)
    if translation:
        db.session.delete(translation)
        db.session.commit()
        flash('Translation deleted!')
    else:
        flash('Translation not found!')
    return redirect(request.referrer)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    # Delete all translations for this user
    Translation.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('User and all their translations have been deleted.')
    return redirect(url_for('admin'))

@app.route('/account_details', methods=['GET', 'POST'])
@login_required
def account_details():
    if request.method == 'POST':
        current_user.account_name = request.form['account_name']
        current_user.account_number = request.form['account_number']
        current_user.bank_name = request.form['bank_name']
        db.session.commit()
        flash("Thank you! Your translations will be reviewed. If approved, your reward will be credited to your account.")
        return redirect('/account_details')
    return render_template('account_details.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_languages()
        # Add English sentences if not already present
        if Sentence.query.count() == 0:
            sentences = [
                "Hello", "Hi", "Good morning", "Good afternoon", "Good evening", "Good night", "Goodbye", "Bye",
                "Please", "Thank you", "You’re welcome", "Sorry", "Excuse me", "Yes", "No", "Maybe", "See you later",
                "Have a nice day", "How are you?", "I’m fine", "What is your name?", "My name is...", "Where are you from?",
                "I am from...", "How old are you?", "What do you do?", "Do you speak English?", "What is this?", "What is that?",
                "Where is it?", "Who is that?", "Why?", "When?", "How?", "How much?", "How many?", "Can you help me?",
                "Do you understand?", "I don’t understand", "What time is it?", "Go", "Come", "Eat", "Drink", "Sleep", "Sit",
                "Stand", "Walk", "Run", "Talk", "Speak", "See", "Look", "Hear", "Listen", "Work", "Play", "Do", "Make", "Want",
                "Man", "Woman", "Child", "Boy", "Girl", "Friend", "Father", "Mother", "Brother", "Sister", "Teacher", "Student",
                "School", "House", "Room", "Food", "Water", "Market", "Town", "Road", "Job", "Work", "Money", "Book", "Phone",
                "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
                "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen", "Twenty", "Monday", "Tuesday",
                "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Today", "Tomorrow", "Yesterday", "Morning",
                "Afternoon", "Evening", "Night", "Now", "Later", "Always", "Never", "Sometimes", "Very", "A little", "A lot",
                "Quickly", "Slowly", "Again"
            ]
            for text in sentences:
                db.session.add(Sentence(english_text=text))
            db.session.commit()
        # Create initial admin user if none exists
        if not User.query.filter_by(is_admin=True).first():
            admin_user = User(
                username="admin",
                phone="080",
                password=generate_password_hash("layun1076"),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True)