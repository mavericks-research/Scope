from flask import Blueprint, render_template, request # Added request
from flask_login import login_required

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/')
@login_required
def index():
    access_token = request.args.get('access_token') # Get token from query param
    return render_template('index.html', access_token=access_token) # Pass to template
