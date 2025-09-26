from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import sqlite3
import hashlib
import datetime
import sys
import io
import requests
import os
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'python_learning_secret_key')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL and psycopg2

def get_db_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        return sqlite3.connect('python_learning.db')

def execute_query(query, params=None, fetch=False):
    conn = get_db_connection()
    if USE_POSTGRES:
        cur = conn.cursor(RealDictCursor())
        cur.execute(query, params or ())
        if fetch:
            result = cur.fetchall()
        else:
            result = cur.rowcount
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            result = cur.fetchall()
        else:
            result = cur.rowcount
        conn.commit()
    conn.close()
    return result

# Khởi tạo database
def init_db():
    conn = get_db_connection()
    
    if USE_POSTGRES:
        cur = conn.cursor()
        
        # Bảng người dùng
        cur.execute('''CREATE TABLE IF NOT EXISTS users
                     (id SERIAL PRIMARY KEY, username VARCHAR(255) UNIQUE, password VARCHAR(255), created_at TIMESTAMP)''')
        
        # Bảng câu hỏi
        cur.execute('''CREATE TABLE IF NOT EXISTS questions
                     (id SERIAL PRIMARY KEY, title TEXT, content TEXT, author VARCHAR(255), created_at TIMESTAMP, answers INTEGER DEFAULT 0)''')
        
        # Bảng câu trả lời
        cur.execute('''CREATE TABLE IF NOT EXISTS answers
                     (id SERIAL PRIMARY KEY, question_id INTEGER, content TEXT, author VARCHAR(255), created_at TIMESTAMP)''')
        
        # Bảng bài học
        cur.execute('''CREATE TABLE IF NOT EXISTS lessons
                     (id SERIAL PRIMARY KEY, title TEXT, content TEXT, code_example TEXT, 
                      exercise TEXT, video_url TEXT, author VARCHAR(255), created_at TIMESTAMP, 
                      status VARCHAR(50) DEFAULT 'approved', type VARCHAR(50) DEFAULT 'course')''')
        
        # Bảng lời giải
        cur.execute('''CREATE TABLE IF NOT EXISTS solutions
                     (id SERIAL PRIMARY KEY, lesson_id INTEGER, solution_code TEXT, explanation TEXT)''')
        
        # Bảng liên hệ
        cur.execute('''CREATE TABLE IF NOT EXISTS contacts
                     (id SERIAL PRIMARY KEY, username VARCHAR(255), subject TEXT, message TEXT, created_at TIMESTAMP)''')
        
        conn.commit()
        cur.close()
    else:
        c = conn.cursor()
        
        # Bảng người dùng
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, created_at TEXT)''')
        
        # Bảng câu hỏi
        c.execute('''CREATE TABLE IF NOT EXISTS questions
                     (id INTEGER PRIMARY KEY, title TEXT, content TEXT, author TEXT, created_at TEXT, answers INTEGER DEFAULT 0)''')
        
        # Bảng câu trả lời
        c.execute('''CREATE TABLE IF NOT EXISTS answers
                     (id INTEGER PRIMARY KEY, question_id INTEGER, content TEXT, author TEXT, created_at TEXT)''')
        
        # Tạo bảng lessons với đầy đủ cột
        c.execute('''CREATE TABLE IF NOT EXISTS lessons
                     (id INTEGER PRIMARY KEY, title TEXT, content TEXT, code_example TEXT, 
                      exercise TEXT, video_url TEXT, author TEXT, created_at TEXT, 
                      status TEXT DEFAULT 'approved', type TEXT DEFAULT 'course')''')
        
        # Bảng lời giải
        c.execute('''CREATE TABLE IF NOT EXISTS solutions
                     (id INTEGER PRIMARY KEY, lesson_id INTEGER, solution_code TEXT, explanation TEXT)''')
        
        conn.commit()
    
    conn.close()

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/lessons')
def lessons():
    lessons = execute_query('SELECT * FROM lessons WHERE status = %s ORDER BY created_at DESC' if USE_POSTGRES else 'SELECT * FROM lessons WHERE status = ? ORDER BY created_at DESC', ('approved',), fetch=True)
    return render_template('lessons.html', lessons=lessons)

@app.route('/code_editor')
def code_editor():
    return render_template('code_editor.html')

@app.route('/lesson/<int:lesson_id>')
def lesson_detail(lesson_id):
    lessons = execute_query('SELECT * FROM lessons WHERE id = %s' if USE_POSTGRES else 'SELECT * FROM lessons WHERE id = ?', (lesson_id,), fetch=True)
    if lessons:
        return render_template('lesson_detail.html', lesson=lessons[0])
    return redirect(url_for('lessons'))

@app.route('/run_code', methods=['POST'])
def run_code():
    code = request.json.get('code', '')
    try:
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        exec(code)
        
        output = captured_output.getvalue()
        sys.stdout = old_stdout
        
        return jsonify({'success': True, 'output': output})
    except Exception as e:
        sys.stdout = old_stdout
        return jsonify({'success': False, 'error': str(e)})



@app.route('/qa')
def qa():
    if 'username' not in session:
        flash('Vui lòng đăng nhập để sử dụng hỏi đáp!')
        return redirect(url_for('auth'))
    
    questions = execute_query('SELECT * FROM questions ORDER BY created_at DESC LIMIT 20', fetch=True)
    return render_template('qa.html', questions=questions)

@app.route('/ask_question', methods=['GET', 'POST'])
def ask_question():
    if 'username' not in session:
        return redirect(url_for('auth'))
        
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = session['username']
        
        query = 'INSERT INTO questions (title, content, author, created_at) VALUES (%s, %s, %s, %s)' if USE_POSTGRES else 'INSERT INTO questions (title, content, author, created_at) VALUES (?, ?, ?, ?)'
        execute_query(query, (title, content, author, datetime.datetime.now().isoformat()))
        
        flash('Câu hỏi đã được đăng!')
        return redirect(url_for('qa'))
    
    return render_template('ask_question.html')

@app.route('/question/<int:question_id>')
def view_question(question_id):
    if 'username' not in session:
        return redirect(url_for('auth'))
        
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('SELECT * FROM questions WHERE id = ?', (question_id,))
    question = c.fetchone()
    c.execute('SELECT * FROM answers WHERE question_id = ? ORDER BY created_at', (question_id,))
    answers = c.fetchall()
    conn.close()
    
    if question:
        return render_template('question_detail.html', question=question, answers=answers)
    return redirect(url_for('qa'))

@app.route('/answer_question/<int:question_id>', methods=['POST'])
def answer_question(question_id):
    if 'username' not in session:
        return redirect(url_for('auth'))
        
    content = request.form['content']
    author = session['username']
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('INSERT INTO answers (question_id, content, author, created_at) VALUES (?, ?, ?, ?)',
             (question_id, content, author, datetime.datetime.now().isoformat()))
    c.execute('UPDATE questions SET answers = answers + 1 WHERE id = ?', (question_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('view_question', question_id=question_id))

@app.route('/ai_chat')
def ai_chat():
    if 'username' not in session:
        flash('Vui lòng đăng nhập để sử dụng AI trợ lý!')
        return redirect(url_for('auth'))
    return render_template('ai_chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    message = request.json.get('message', '')
    
    try:
        headers = {
            'Authorization': 'Bearer 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',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'openai/gpt-oss-120b',
            'messages': [
                {
                    'role': 'system',
                    'content': 'Bạn là AI trợ lý Python. Trả lời ngắn gọn, không dùng ký tự đặc biệt như * | `. Code phải xuống dòng rõ ràng. Tối đa 3-4 câu.'
                },
                {
                    'role': 'user', 
                    'content': message
                }
            ],
            'max_tokens': 200,
            'temperature': 0.3
        }
        
        response = requests.post('https://api.groq.com/openai/v1/chat/completions', 
                               headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            return jsonify({'response': ai_response})
        else:
            return jsonify({'response': 'AI đang bận. Thử lại sau!'})
            
    except Exception as e:
        fallback_responses = {
            'xin chào': 'Chào bạn! Tôi giúp học Python.',
            'hello': 'Hi! Tôi giúp học Python.',
            'python': 'Python dễ học. Bạn cần gì?'
        }
        
        response_text = "Tôi giúp học Python."
        for key, value in fallback_responses.items():
            if key in message.lower():
                response_text = value
                break
                
        return jsonify({'response': response_text})



@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        current_username = session['username']
        
        conn = sqlite3.connect('python_learning.db')
        c = conn.cursor()
        
        if new_password:
            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            c.execute('UPDATE users SET username = ?, password = ? WHERE username = ?',
                     (new_username, hashed_password, current_username))
        else:
            c.execute('UPDATE users SET username = ? WHERE username = ?',
                     (new_username, current_username))
        
        conn.commit()
        conn.close()
        
        session['username'] = new_username
        flash('Cập nhật thông tin thành công!')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if 'username' not in session:
        flash('Vui lòng đăng nhập để liên hệ!')
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        subject = request.form['subject']
        message = request.form['message']
        username = session['username']
        
        # Lưu tin nhắn liên hệ vào database
        conn = sqlite3.connect('python_learning.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS contacts
                     (id INTEGER PRIMARY KEY, username TEXT, subject TEXT, message TEXT, created_at TEXT)''')
        c.execute('INSERT INTO contacts (username, subject, message, created_at) VALUES (?, ?, ?, ?)',
                 (username, subject, message, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        flash('Tin nhắn đã được gửi thành công! Cảm ơn bạn đã gửi tin nhắn liên hệ với ADMIN!')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

# Admin routes
@app.route('/admin/create_lesson', methods=['GET', 'POST'])
def admin_create_lesson():
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        code_example = request.form.get('code_example', '')
        exercise = request.form.get('exercise', '')
        video_url = request.form.get('video_url', '')
        solution_code = request.form.get('solution_code', '')
        solution_explanation = request.form.get('solution_explanation', '')
        
        conn = sqlite3.connect('python_learning.db')
        c = conn.cursor()
        c.execute('INSERT INTO lessons (title, content, code_example, exercise, video_url, author, created_at, status, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (title, content, code_example, exercise, video_url, 'admin', datetime.datetime.now().isoformat(), 'approved', 'lesson'))
        
        lesson_id = c.lastrowid
        if solution_code:
            c.execute('INSERT INTO solutions (lesson_id, solution_code, explanation) VALUES (?, ?, ?)',
                     (lesson_id, solution_code, solution_explanation))
        
        conn.commit()
        conn.close()
        
        flash('Bài học đã được tạo!')
        return redirect(url_for('lessons'))
    
    return render_template('admin_create_lesson.html')



# Contribute routes
@app.route('/contribute_lesson', methods=['GET', 'POST'])
def contribute_lesson():
    if 'username' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        code_example = request.form.get('code_example', '')
        exercise = request.form.get('exercise', '')
        video_url = request.form.get('video_url', '')
        solution_code = request.form.get('solution_code', '')
        solution_explanation = request.form.get('solution_explanation', '')
        
        conn = sqlite3.connect('python_learning.db')
        c = conn.cursor()
        c.execute('INSERT INTO lessons (title, content, code_example, exercise, video_url, author, created_at, status, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (title, content, code_example, exercise, video_url, session['username'], datetime.datetime.now().isoformat(), 'pending', 'lesson'))
        
        lesson_id = c.lastrowid
        if solution_code:
            c.execute('INSERT INTO solutions (lesson_id, solution_code, explanation) VALUES (?, ?, ?)',
                     (lesson_id, solution_code, solution_explanation))
        
        conn.commit()
        conn.close()
        
        flash('Đã gửi bài học để admin duyệt!')
        return redirect(url_for('lessons'))
    
    return render_template('contribute_lesson.html')





# Review routes
@app.route('/review_lesson_contributions')
def review_lesson_contributions():
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('SELECT * FROM lessons WHERE status = "pending" ORDER BY created_at DESC')
    contributions = c.fetchall()
    conn.close()
    
    return render_template('review_lesson_contributions.html', contributions=contributions)







@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('python_learning.db')
        c = conn.cursor()
        
        if action == 'register':
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            try:
                c.execute('INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)',
                         (username, hashed_password, datetime.datetime.now().isoformat()))
                conn.commit()
                session['username'] = username
                flash('Chúc mừng bạn đã đăng ký thành công!')
                conn.close()
                return redirect(url_for('home'))
            except sqlite3.IntegrityError:
                flash('Tên người dùng đã tồn tại!')
                conn.close()
        
        elif action == 'login':
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_password))
            user = c.fetchone()
            conn.close()
            
            if user:
                session['username'] = username
                flash('Chúc mừng bạn đã đăng nhập thành công!')
                return redirect(url_for('home'))
            else:
                flash('Sai tên đăng nhập hoặc mật khẩu!')
    
    return render_template('auth.html')

@app.route('/login')
def login():
    return redirect(url_for('auth'))

@app.route('/register')
def register():
    return redirect(url_for('auth'))

@app.route('/approve_lesson/<int:lesson_id>')
def approve_lesson(lesson_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('UPDATE lessons SET status = "approved" WHERE id = ?', (lesson_id,))
    conn.commit()
    conn.close()
    
    flash('Bài học đã được duyệt!')
    return redirect(url_for('lessons'))

@app.route('/reject_lesson/<int:lesson_id>')
def reject_lesson(lesson_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('UPDATE lessons SET status = "rejected" WHERE id = ?', (lesson_id,))
    conn.commit()
    conn.close()
    
    flash('Bài học đã bị từ chối!')
    return redirect(url_for('lessons'))



@app.route('/get_solution/<int:lesson_id>')
def get_solution(lesson_id):
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('SELECT solution_code, explanation FROM solutions WHERE lesson_id = ?', (lesson_id,))
    solution = c.fetchone()
    conn.close()
    
    if solution:
        return jsonify({'solution': solution[0], 'explanation': solution[1]})
    else:
        return jsonify({'solution': None})

@app.route('/admin/edit_lesson/<int:lesson_id>', methods=['GET', 'POST'])
def admin_edit_lesson(lesson_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        code_example = request.form.get('code_example', '')
        exercise = request.form.get('exercise', '')
        video_url = request.form.get('video_url', '')
        
        c.execute('UPDATE lessons SET title = ?, content = ?, code_example = ?, exercise = ?, video_url = ? WHERE id = ?',
                 (title, content, code_example, exercise, video_url, lesson_id))
        conn.commit()
        conn.close()
        
        flash('Bài học đã được cập nhật!')
        return redirect(url_for('lessons'))
    
    c.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,))
    lesson = c.fetchone()
    conn.close()
    
    return render_template('admin_edit_lesson.html', lesson=lesson)

@app.route('/admin/delete_lesson/<int:lesson_id>')
def admin_delete_lesson(lesson_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('DELETE FROM lessons WHERE id = ?', (lesson_id,))
    c.execute('DELETE FROM solutions WHERE lesson_id = ?', (lesson_id,))
    conn.commit()
    conn.close()
    
    flash('Bài học đã được xóa!')
    return redirect(url_for('lessons'))

@app.route('/exercise/<int:lesson_id>')
def exercise_page(lesson_id):
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,))
    lesson = c.fetchone()
    conn.close()
    if lesson:
        return render_template('exercise_page.html', lesson=lesson)
    return redirect(url_for('lessons'))

@app.route('/admin/view_contacts')
def view_contacts():
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('SELECT * FROM contacts ORDER BY created_at DESC')
    contacts = c.fetchall()
    conn.close()
    
    return render_template('view_contacts.html', contacts=contacts)

@app.route('/admin/delete_question/<int:question_id>')
def delete_question(question_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('DELETE FROM answers WHERE question_id = ?', (question_id,))
    c.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    conn.commit()
    conn.close()
    
    flash('Câu hỏi đã được xóa!')
    return redirect(url_for('qa'))

@app.route('/admin/delete_contact/<int:contact_id>')
def delete_contact(contact_id):
    if session.get('username') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('python_learning.db')
    c = conn.cursor()
    c.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
    conn.commit()
    conn.close()
    
    flash('Tin nhắn liên hệ đã được xóa!')
    return redirect(url_for('view_contacts'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Đã đăng xuất!')
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    
    # Tạo admin
    admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
    try:
        query = 'INSERT INTO users (username, password, created_at) VALUES (%s, %s, %s)' if USE_POSTGRES else 'INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)'
        execute_query(query, ('admin', admin_password, datetime.datetime.now().isoformat()))
    except:
        pass
    
    port = int(os.environ.get('PORT', 5000))
    debug = not os.environ.get('DATABASE_URL')
    
    if debug:
        print('\nWeb: http://localhost:5000')
        print('Admin: admin / admin123')
    
    app.run(debug=debug, host='0.0.0.0', port=port)