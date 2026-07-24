from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'truthscan-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///truthscan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ─── MODELS ──────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    detections = db.relationship('Detection', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    article_text = db.Column(db.Text, nullable=False)
    article_preview = db.Column(db.String(200))
    result = db.Column(db.String(10), nullable=False)   # 'REAL' or 'FAKE'
    confidence = db.Column(db.Float, nullable=False)
    bert_score = db.Column(db.Float)
    bilstm_score = db.Column(db.Float)
    xgboost_score = db.Column(db.Float)
    word_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── PREDICTION HELPER ───────────────────────────────────────────────────────

def predict_article(text):
    """
    Simulates the stacking ensemble prediction.
    Replace the body of this function with your real model inference
    once you export your trained models from Kaggle.
    """
    word_count = len(text.split())
    words = text.lower()

    fake_signals = [
        'breaking', 'shocking', 'exclusive', 'conspiracy', 'secret',
        'mainstream media', 'they dont want you', 'wake up', 'hoax',
        'fake', 'fraud', 'lie', 'cover-up', 'exposed', 'banned',
        'censored', 'truth about', 'you wont believe'
    ]
    real_signals = [
        'according to', 'said in a statement', 'confirmed', 'reported',
        'study found', 'research shows', 'official', 'spokesperson',
        'percent', 'data', 'survey', 'analysis', 'published'
    ]

    fake_count = sum(1 for w in fake_signals if w in words)
    real_count = sum(1 for w in real_signals if w in words)

    base = 0.5 + (real_count * 0.04) - (fake_count * 0.06)
    base = max(0.1, min(0.97, base))
    noise = random.uniform(-0.05, 0.05)
    real_prob = max(0.05, min(0.97, base + noise))

    bert_score    = round(real_prob + random.uniform(-0.02, 0.02), 4)
    bilstm_score  = round(real_prob + random.uniform(-0.02, 0.02), 4)
    xgboost_score = round(real_prob + random.uniform(-0.03, 0.03), 4)

    ensemble_prob = (bert_score * 0.4 + bilstm_score * 0.35 + xgboost_score * 0.25)
    ensemble_prob = round(max(0.01, min(0.99, ensemble_prob)), 4)

    result = 'REAL' if ensemble_prob >= 0.5 else 'FAKE'
    confidence = ensemble_prob if result == 'REAL' else (1 - ensemble_prob)

    return {
        'result': result,
        'confidence': round(confidence * 100, 1),
        'bert_score': round(bert_score * 100, 1),
        'bilstm_score': round(bilstm_score * 100, 1),
        'xgboost_score': round(xgboost_score * 100, 1),
        'word_count': word_count,
        'article_preview': text[:180] + '...' if len(text) > 180 else text
    }


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    total = Detection.query.count()
    fake_count = Detection.query.filter_by(result='FAKE').count()
    real_count = Detection.query.filter_by(result='REAL').count()
    recent = Detection.query.order_by(Detection.created_at.desc()).limit(5).all()
    return render_template('index.html',
                           total=total, fake_count=fake_count,
                           real_count=real_count, recent=recent)


@app.route('/detect', methods=['GET', 'POST'])
def detect():
    if request.method == 'POST':
        text = request.form.get('article_text', '').strip()
        if len(text) < 30:
            flash('Please enter at least 30 characters.', 'error')
            return render_template('detect.html')

        pred = predict_article(text)

        detection = Detection(
            user_id=session.get('user_id'),
            article_text=text,
            article_preview=pred['article_preview'],
            result=pred['result'],
            confidence=pred['confidence'],
            bert_score=pred['bert_score'],
            bilstm_score=pred['bilstm_score'],
            xgboost_score=pred['xgboost_score'],
            word_count=pred['word_count']
        )
        db.session.add(detection)
        db.session.commit()

        return redirect(url_for('result', detection_id=detection.id))

    return render_template('detect.html')


@app.route('/result/<int:detection_id>')
def result(detection_id):
    detection = Detection.query.get_or_404(detection_id)
    return render_template('result.html', d=detection)


@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Please log in to view your history.', 'error')
        return redirect(url_for('login'))
    detections = Detection.query.filter_by(
        user_id=session['user_id']
    ).order_by(Detection.created_at.desc()).all()
    return render_template('history.html', detections=detections)


@app.route('/dashboard')
def dashboard():
    total = Detection.query.count()
    fake_count = Detection.query.filter_by(result='FAKE').count()
    real_count = Detection.query.filter_by(result='REAL').count()
    fake_pct = round((fake_count / total * 100), 1) if total else 0
    real_pct = round((real_count / total * 100), 1) if total else 0

    # Monthly data for chart (last 6 months)
    monthly_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    monthly_fake   = [random.randint(20, 80) for _ in range(6)]
    monthly_real   = [random.randint(30, 90) for _ in range(6)]

    model_metrics = {
        'BERT':     {'accuracy': 98.28, 'f1': 98.28, 'precision': 98.30, 'recall': 98.28},
        'BiLSTM':   {'accuracy': 98.68, 'f1': 98.68, 'precision': 98.68, 'recall': 98.68},
        'XGBoost':  {'accuracy': 96.60, 'f1': 96.72, 'precision': 97.00, 'recall': 96.60},
        'Ensemble': {'accuracy': 98.66, 'f1': 99.94, 'precision': 98.66, 'recall': 98.66},
    }

    return render_template('dashboard.html',
                           total=total, fake_count=fake_count,
                           real_count=real_count, fake_pct=fake_pct,
                           real_pct=real_pct,
                           monthly_labels=monthly_labels,
                           monthly_fake=monthly_fake,
                           monthly_real=monthly_real,
                           model_metrics=model_metrics)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('register.html')
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session['username'] = user.username
        flash('Account created! Welcome to TruthScan.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/api/stats')
def api_stats():
    total = Detection.query.count()
    fake  = Detection.query.filter_by(result='FAKE').count()
    real  = Detection.query.filter_by(result='REAL').count()
    return jsonify({'total': total, 'fake': fake, 'real': real})


# ─── INIT ────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
