__FILENAME__ = app
"""
My Flask website.
"""

from flask import Flask, render_template
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/cfa')
def cfa():
    return render_template('cfa.html')


if __name__ == '__main__':
    app.run(debug=True)

########NEW FILE########
