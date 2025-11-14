# app.py -- CampusConnect (strict ER/RS)
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "supersecret"  # change in production

# --- DB config: update password ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root123',   # <<-- PUT YOUR MYSQL PASSWORD HERE
    'database': 'dbms_project'
}

def get_db():
    return mysql.connector.connect(**db_config)

# safe year normalization
def normalize_year(value):
    if value is None:
        return None
    v = str(value).strip().lower()
    mapping = {
        "1": 1, "1st": 1, "first": 1,
        "2": 2, "2nd": 2, "second": 2,
        "3": 3, "3rd": 3, "third": 3,
        "4": 4, "4th": 4, "fourth": 4
    }
    return mapping.get(v, None)

# generate next numeric id if user omitted (keeps strict schema)
def next_id(table, col):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT MAX({col}) FROM `{table}`")
    r = cur.fetchone()
    cur.close(); conn.close()
    if r and r[0]:
        try:
            return int(r[0]) + 1
        except:
            return 1
    return 1

# inject default lists into all templates to avoid errors
@app.context_processor
def inject_defaults():
    return {'popular_tags': [], 'quick_channels': [], 'all_channels': []}

# load logged-in user
@app.before_request
def load_logged_in_user():
    g.user = None
    if 'user_id' in session:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM `USER` WHERE user_id = %s", (session['user_id'],))
        g.user = cur.fetchone()
        cur.close(); conn.close()

def next_user_id():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(user_id), 0) + 1 FROM USER")
    new_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return new_id


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':

        # auto-generate next user_id
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(user_id), 0) + 1 FROM USER")
        user_id = cur.fetchone()[0]

        # required fields
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()

        if not (name and email and password):
            flash("Name, email, and password are required.")
            return redirect(url_for('register'))

        # hash password -> store into password_hash column (matches schema)
        password_hash = generate_password_hash(password)

        # numeric year only
        raw_year = request.form.get('year','').strip()
        year = int(raw_year) if raw_year.isdigit() else None

        department = request.form.get('department','').strip()
        bio = request.form.get('bio','').strip()
        created_on = datetime.now().date()

        try:
            cur.execute("""
                INSERT INTO USER
                (user_id, name, email, password_hash, year, department, bio, created_on)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (user_id, name, email, password_hash, year, department, bio, created_on))

            conn.commit()
            flash("Registered. Please log in.")
            return redirect(url_for('login'))

        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Error: {e}")

        finally:
            cur.close()
            conn.close()

    return render_template('register.html')




@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM USER WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            flash("No account with that email.")
            return redirect(url_for('login'))

        # CHECK PASSWORD CORRECTLY
        if not check_password_hash(user['password_hash'], password):
            flash("Incorrect password.")
            return redirect(url_for('login'))

        # SUCCESS
        session.clear()
        session['user_id'] = user['user_id']
        flash("Logged in successfully.")
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET','POST'])
def profile():
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form.get('name', g.user['name'])
        bio = request.form.get('bio', g.user.get('bio',''))
        department = request.form.get('department', g.user.get('department',''))
        year = normalize_year(request.form.get('year')) or g.user.get('year')
        cur.execute("UPDATE `USER` SET name=%s, bio=%s, department=%s, year=%s WHERE user_id=%s",
                    (name, bio, department, year, g.user['user_id']))
        conn.commit()
        cur.close(); conn.close()
        flash('Profile updated'); return redirect(url_for('profile'))
    cur.execute("SELECT * FROM `USER` WHERE user_id=%s", (g.user['user_id'],))
    user = cur.fetchone()
    cur.close(); conn.close()
    return render_template('profile.html', user=user)

# ---------- HOME / FEED ----------
@app.route('/')
def index():
    if not g.user:
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # POSTS + USER + CHANNEL + COMMENT COUNT
    cur.execute("""
        SELECT 
            p.*, 
            u.name AS user_name, 
            c.channel_name,
            commentCount(p.post_id) AS comment_count
        FROM `POST` p
        LEFT JOIN `USER` u ON p.user_id = u.user_id
        LEFT JOIN `CHANNEL` c ON p.channel_id = c.channel_id
        ORDER BY p.Created_on DESC
    """)
    posts = cur.fetchall()

    # composer dropdown
    cur.execute("SELECT channel_id, channel_name FROM `CHANNEL`")
    all_channels = cur.fetchall()

    # sidebar popular tags
    cur.execute("SELECT tag_id, tag_name FROM `TAG` LIMIT 8")
    popular_tags = cur.fetchall()

    # sidebar quick channels
    cur.execute("SELECT channel_id, channel_name FROM `CHANNEL` LIMIT 6")
    quick_channels = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'feed.html',
        posts=posts,
        all_channels=all_channels,
        popular_tags=popular_tags,
        quick_channels=quick_channels
    )


# ---------- CHANNELS ----------
@app.route('/channels')
def channels():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM `CHANNEL`")
    chs = cur.fetchall()
    joined = set()
    if g.user:
        cur.execute("SELECT Channel_id FROM `User_channel` WHERE User_id=%s", (g.user['user_id'],))
        joined = {row['Channel_id'] for row in cur.fetchall()}
    cur.close(); conn.close()
    return render_template('channels.html', channels=chs, joined=joined)

@app.route('/channel/add', methods=['GET','POST'])
def add_channel():
    if not g.user:
        return redirect(url_for('login'))

    if request.method == 'POST':

        # AUTO GENERATE NEXT channel_id
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(channel_id), 0) + 1 FROM CHANNEL")
        channel_id = cur.fetchone()[0]

        channel_name = request.form.get('channel_name','').strip()
        description = request.form.get('description','').strip()

        if not channel_name:
            flash("Channel name required")
            return redirect(url_for('add_channel'))

        try:
            cur.execute("""
                INSERT INTO CHANNEL (channel_id, channel_name, description)
                VALUES (%s, %s, %s)
            """, (channel_id, channel_name, description))

            conn.commit()
            flash("Channel created!")
            return redirect(url_for('channels'))

        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Error: {e}")

        finally:
            cur.close()
            conn.close()

    return render_template('add_channel.html')


@app.route('/channel/join/<int:ch_id>')
def join_channel(ch_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO `User_channel` (User_id, Channel_id) VALUES (%s,%s)", (g.user['user_id'], ch_id))
        conn.commit(); flash('Joined channel')
    except mysql.connector.Error:
        conn.rollback(); flash('Already joined or error')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('channels'))

@app.route('/channel/leave/<int:ch_id>')
def leave_channel(ch_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM `User_channel` WHERE User_id=%s AND Channel_id=%s", (g.user['user_id'], ch_id))
    conn.commit(); cur.close(); conn.close()
    flash('Left channel')
    return redirect(url_for('channels'))

# channel messages view
@app.route('/channel/<int:ch_id>/messages', methods=['GET','POST'])
def channel_messages(ch_id):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        if not g.user: return redirect(url_for('login'))
        raw = request.form.get('message_id','').strip()
        message_id = int(raw) if raw.isdigit() else next_id('MESSAGE','message_id')
        message_text = request.form.get('message_text','').strip()
        timestamp = request.form.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("INSERT INTO `MESSAGE` (message_id,user_id,channel_id,message_text,timestamp) VALUES (%s,%s,%s,%s,%s)",
                    (message_id, g.user['user_id'], ch_id, message_text, timestamp))
        conn.commit(); flash('Message sent')
        return redirect(url_for('channel_messages', ch_id=ch_id))
    cur.execute("SELECT m.*, u.name AS user_name FROM `MESSAGE` m LEFT JOIN `USER` u ON m.user_id = u.user_id WHERE m.channel_id=%s ORDER BY m.timestamp DESC", (ch_id,))
    msgs = cur.fetchall()
    cur.close(); conn.close()
    return render_template('channel_messages.html', messages=msgs, ch_id=ch_id)

# ---------- POSTS ----------
@app.route('/posts')
def posts():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT p.*, u.name AS user_name, c.channel_name 
                   FROM `POST` p LEFT JOIN `USER` u ON p.user_id=u.user_id
                   LEFT JOIN `CHANNEL` c ON p.channel_id=c.channel_id
                   ORDER BY p.Created_on DESC""")
    posts = cur.fetchall()
    cur.close(); conn.close()
    return render_template('posts.html', posts=posts)

@app.route('/post/add', methods=['GET','POST'])
def add_post():
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        raw = request.form.get('post_id','').strip()
        post_id = int(raw) if raw.isdigit() else next_id('POST','post_id')
        user_id = g.user['user_id']
        title = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        category = request.form.get('category','').strip()
        Created_on = request.form.get('Created_on') or datetime.now().date()
        channel_id = int(request.form.get('channel_id'))
        likes = int(request.form.get('likes')) if request.form.get('likes','').isdigit() else 0
        # insert
        cur2 = conn.cursor()
        cur2.execute("""INSERT INTO `POST` (post_id,user_id,title,content,category,Created_on,channel_id,likes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (post_id, user_id, title, content, category, Created_on, channel_id, likes))
        conn.commit()
        # tags mapping
        tags_input = request.form.get('tags','').strip()
        if tags_input:
            tags = [t.strip() for t in re.split(r'[,\s]+', tags_input) if t.strip()]
            for tg in tags:
                if tg.isdigit():
                    tid = int(tg)
                else:
                    tid = next_id('TAG','tag_id')
                    try:
                        cur2.execute("INSERT INTO `TAG` (tag_id, tag_name) VALUES (%s,%s)", (tid, tg))
                        conn.commit()
                    except mysql.connector.Error:
                        conn.rollback()
                try:
                    cur2.execute("INSERT INTO `Post_tag` (Post_id, Tag_id) VALUES (%s,%s)", (post_id, tid))
                    conn.commit()
                except mysql.connector.Error:
                    conn.rollback()
        cur2.close(); conn.close()
        flash('Post added.'); return redirect(url_for('index'))
    # GET
    cur.execute("SELECT channel_id, channel_name FROM `CHANNEL`")
    channels = cur.fetchall()
    cur.close(); conn.close()
    return render_template('add_post.html', channels=channels)

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # POST — add comment
    if request.method == 'POST':
        if not g.user:
            flash("Login required")
            return redirect(url_for('login'))

        # auto-generate comment_id
        cur.execute("SELECT COALESCE(MAX(comment_id), 0) + 1 AS next_id FROM COMMENT")
        comment_id = cur.fetchone()['next_id']

        comment_text = request.form['comment_text']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO COMMENT (comment_id, post_id, user_id, comment_text, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (comment_id, post_id, g.user['user_id'], comment_text, timestamp))

        conn.commit()
        flash("Comment added!")
        return redirect(url_for('view_post', post_id=post_id))

    # GET — fetch post
    cur.execute("""
        SELECT p.*, u.name AS user_name, c.channel_name
        FROM POST p
        JOIN USER u ON p.user_id = u.user_id
        JOIN CHANNEL c ON p.channel_id = c.channel_id
        WHERE p.post_id = %s
    """, (post_id,))
    post = cur.fetchone()

    # comments
    cur.execute("""
        SELECT c.*, u.name AS user_name
        FROM COMMENT c
        JOIN USER u ON c.user_id = u.user_id
        WHERE c.post_id = %s
        ORDER BY c.timestamp DESC
    """, (post_id,))
    comments = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("view_post.html", post=post, comments=comments)

@app.route('/post/<int:post_id>/edit', methods=['GET','POST'])
def edit_post(post_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM `POST` WHERE post_id=%s", (post_id,))
    post = cur.fetchone()
    if not post:
        cur.close(); conn.close(); flash('Post not found'); return redirect(url_for('posts'))
    if post['user_id'] != g.user['user_id']:
        cur.close(); conn.close(); flash('Only owner can edit'); return redirect(url_for('view_post', post_id=post_id))
    if request.method == 'POST':
        title = request.form.get('title', post['title']); content = request.form.get('content', post['content']); category = request.form.get('category', post['category'])
        cur.execute("UPDATE `POST` SET title=%s, content=%s, category=%s WHERE post_id=%s",
                    (title,content,category,post_id))
        conn.commit(); cur.close(); conn.close(); flash('Post updated'); return redirect(url_for('view_post', post_id=post_id))
    cur.close(); conn.close(); return render_template('post_edit.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM `POST` WHERE post_id=%s", (post_id,))
    row = cur.fetchone()
    if not row: cur.close(); conn.close(); flash('Post not found'); return redirect(url_for('posts'))
    if row['user_id'] != g.user['user_id']: cur.close(); conn.close(); flash('Only owner can delete'); return redirect(url_for('view_post', post_id=post_id))
    cur.execute("DELETE FROM `POST` WHERE post_id=%s", (post_id,)); conn.commit(); cur.close(); conn.close(); flash('Post deleted'); return redirect(url_for('index'))

# ---------- COMMENTS ----------
@app.route('/comment/add/<int:post_id>', methods=['POST'])
def add_comment_to_post(post_id):
    if not g.user: return redirect(url_for('login'))
    raw = request.form.get('comment_id','').strip()
    comment_id = int(raw) if raw.isdigit() else next_id('COMMENT','comment_id')
    comment_text = request.form.get('comment_text','').strip()
    timestamp = request.form.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO `COMMENT` (comment_id,post_id,user_id,comment_text,timestamp) VALUES (%s,%s,%s,%s,%s)",
                (comment_id, post_id, g.user['user_id'], comment_text, timestamp))
    conn.commit(); cur.close(); conn.close(); flash('Comment added'); return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<int:comment_id>/edit', methods=['GET','POST'])
def edit_comment(comment_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM `COMMENT` WHERE comment_id=%s", (comment_id,))
    com = cur.fetchone()
    if not com: cur.close(); conn.close(); flash('Comment not found'); return redirect(url_for('index'))
    if com['user_id'] != g.user['user_id']: cur.close(); conn.close(); flash('Only owner can edit'); return redirect(url_for('view_post', post_id=com['post_id']))
    if request.method == 'POST':
        text = request.form.get('comment_text', com['comment_text'])
        cur.execute("UPDATE `COMMENT` SET comment_text=%s WHERE comment_id=%s", (text, comment_id)); conn.commit(); cur.close(); conn.close(); flash('Comment updated'); return redirect(url_for('view_post', post_id=com['post_id']))
    cur.close(); conn.close(); return render_template('comment_edit.html', comment=com)

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM `COMMENT` WHERE comment_id=%s", (comment_id,))
    com = cur.fetchone()
    if not com: cur.close(); conn.close(); flash('Comment not found'); return redirect(url_for('index'))
    if com['user_id'] != g.user['user_id']: cur.close(); conn.close(); flash('Only owner can delete'); return redirect(url_for('view_post', post_id=com['post_id']))
    cur.execute("DELETE FROM `COMMENT` WHERE comment_id=%s", (comment_id,)); conn.commit(); cur.close(); conn.close(); flash('Comment deleted'); return redirect(url_for('view_post', post_id=com['post_id']))

# ---------- LIKES ----------
@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE `POST` SET likes = likes + 1 WHERE post_id=%s", (post_id,))
    conn.commit(); cur.close(); conn.close(); flash('Post liked'); return redirect(url_for('view_post', post_id=post_id))

# ---------- TAGS ----------
@app.route('/tags')
def tags():
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # All tags for the main table
    cur.execute("SELECT tag_id, tag_name FROM TAG ORDER BY tag_name")
    tags = cur.fetchall()

    # Right sidebar: popular tags (first 8)
    cur.execute("SELECT tag_name FROM TAG LIMIT 8")
    popular_tags = cur.fetchall()

    # Right sidebar: quick channels (first 6)
    cur.execute("SELECT channel_id, channel_name FROM CHANNEL LIMIT 6")
    quick_channels = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'tags.html',
        tags=tags,
        popular_tags=popular_tags,
        quick_channels=quick_channels
    )


@app.route('/post_tag/add', methods=['GET','POST'])
def add_post_tag():
    if not g.user: return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        Post_id = int(request.form['Post_id']); Tag_id = int(request.form['Tag_id'])
        cur.execute("INSERT INTO `Post_tag` (Post_id, Tag_id) VALUES (%s,%s)", (Post_id, Tag_id))
        conn.commit(); cur.close(); conn.close(); flash('Tag added to post'); return redirect(url_for('view_post', post_id=Post_id))
    cur.execute("SELECT post_id, title FROM `POST`"); posts = cur.fetchall()
    cur.execute("SELECT tag_id, tag_name FROM `TAG`"); tags = cur.fetchall()
    cur.close(); conn.close()
    return render_template('add_post_tag.html', posts=posts, tags=tags)

# ---------- VIEW POSTS BY TAG ----------
@app.route('/tag/<tag_name>')
def view_tag(tag_name):

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch all posts under this tag
    cur.execute("""
        SELECT 
            p.post_id,
            p.title,
            p.content,
            p.Created_on,
            u.name AS user_name,
            c.channel_name,
            t.tag_name
        FROM POST p
        JOIN Post_tag pt ON p.post_id = pt.Post_id
        JOIN TAG t ON pt.Tag_id = t.tag_id
        JOIN USER u ON p.user_id = u.user_id
        JOIN CHANNEL c ON p.channel_id = c.channel_id
        WHERE t.tag_name = %s
        ORDER BY p.Created_on DESC
    """, (tag_name,))
    
    posts = cur.fetchall()

    # ========== SIDEBAR DATA (REQUIRED) ==========
    cur.execute("SELECT tag_id, tag_name FROM TAG LIMIT 8")
    popular_tags = cur.fetchall()

    cur.execute("SELECT channel_id, channel_name FROM CHANNEL LIMIT 6")
    quick_channels = cur.fetchall()

    cur.close()
    conn.close()

    # Render page
    return render_template(
        "tag_posts.html",
        tag=tag_name,
        posts=posts,
        popular_tags=popular_tags,
        quick_channels=quick_channels
    )



# ---------- SEARCH ----------
@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    results = {'users':[], 'channels':[], 'posts':[]}
    if q:
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT user_id, name FROM `USER` WHERE name LIKE %s", ('%'+q+'%',))
        results['users'] = cur.fetchall()
        cur.execute("SELECT channel_id, channel_name FROM `CHANNEL` WHERE channel_name LIKE %s", ('%'+q+'%',))
        results['channels'] = cur.fetchall()
        cur.execute("SELECT p.post_id, p.title FROM `POST` p WHERE p.title LIKE %s", ('%'+q+'%',))
        results['posts'].extend(cur.fetchall())
        cur.execute("""SELECT p.post_id, p.title FROM `POST` p
                       JOIN `Post_tag` pt ON p.post_id = pt.Post_id
                       JOIN `TAG` t ON pt.Tag_id = t.tag_id
                       WHERE t.tag_name LIKE %s""", ('%'+q+'%',))
        results['posts'].extend(cur.fetchall())
        seen = set(); dedup=[]
        for row in results['posts']:
            if row['post_id'] not in seen:
                seen.add(row['post_id']); dedup.append(row)
        results['posts'] = dedup
        cur.close(); conn.close()
    return render_template('search.html', q=q, results=results)

# ---------- STORED PROC USAGE ----------
@app.route('/channel_posts/<int:ch_id>')
def channel_posts(ch_id):
    conn = get_db(); cur = conn.cursor()
    cur.callproc('GetPostsByChannel', [ch_id])
    rows = []
    for result in cur.stored_results():
        rows = result.fetchall()
    cur.close(); conn.close()
    return render_template('channel_posts.html', rows=rows, ch_id=ch_id)

if __name__ == '__main__':
    app.run(debug=True)
