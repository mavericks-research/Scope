from flask import Blueprint, render_template
from flask_login import login_required

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/')
@login_required
def index():
    return render_template('index.html')
