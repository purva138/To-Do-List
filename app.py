from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date

app = Flask(__name__)


def init_db():
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'Medium',
            due_date TEXT DEFAULT NULL
        )
    """)

    cursor.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in cursor.fetchall()]

    if "priority" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'Medium'")

    if "due_date" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT DEFAULT NULL")

    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect("todo.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks")
    all_tasks = cursor.fetchall()
    conn.close()

    today_str = date.today().isoformat()

    total = len(all_tasks)
    active = sum(1 for t in all_tasks if not t["completed"])
    completed = sum(1 for t in all_tasks if t["completed"])
    high_priority = sum(1 for t in all_tasks if t["priority"] == "High")
    overdue = sum(
        1 for t in all_tasks
        if not t["completed"] and t["due_date"] and t["due_date"] < today_str
    )

    return {
        "total": total,
        "active": active,
        "completed": completed,
        "high_priority": high_priority,
        "overdue": overdue
    }


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        task_name = request.form.get("task", "").strip()
        priority = request.form.get("priority", "Medium")
        due_date = request.form.get("due_date", "").strip() or None

        if task_name:
            conn = sqlite3.connect("todo.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (task, priority, due_date) VALUES (?, ?, ?)",
                (task_name, priority, due_date)
            )
            conn.commit()
            conn.close()

        return redirect(url_for("home"))

    search_query = request.args.get("search", "").strip()
    filter_by = request.args.get("filter", "all").lower()
    sort_by = request.args.get("sort", "newest").lower()

    today_str = date.today().isoformat()

    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if search_query:
        sql += " AND task LIKE ?"
        params.append(f"%{search_query}%")

    if filter_by == "active":
        sql += " AND completed = 0"
    elif filter_by == "completed":
        sql += " AND completed = 1"
    elif filter_by == "high":
        sql += " AND priority = 'High'"
    elif filter_by == "medium":
        sql += " AND priority = 'Medium'"
    elif filter_by == "low":
        sql += " AND priority = 'Low'"
    elif filter_by == "overdue":
        sql += " AND completed = 0 AND due_date IS NOT NULL AND due_date != '' AND due_date < ?"
        params.append(today_str)

    if sort_by == "oldest":
        sql += " ORDER BY id ASC"
    elif sort_by == "priority":
        sql += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END ASC, id DESC"
    elif sort_by == "due_date":
        sql += " ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC, id DESC"
    else:  # newest
        sql += " ORDER BY id DESC"

    conn = sqlite3.connect("todo.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql, params)
    tasks = cursor.fetchall()
    conn.close()

    stats = get_stats()

    return render_template(
        "index.html",
        tasks=tasks,
        stats=stats,
        search=search_query,
        current_filter=filter_by,
        current_sort=sort_by,
        today=today_str
    )


@app.route("/delete/<int:task_id>")
def delete_task(task_id):
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("home"))


@app.route("/complete/<int:task_id>")
@app.route("/toggle/<int:task_id>")
def complete_task(task_id):
    conn = sqlite3.connect("todo.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT completed FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if task:
        new_status = 0 if task["completed"] else 1
        cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (new_status, task_id))
        conn.commit()

    conn.close()
    return redirect(request.referrer or url_for("home"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    conn = sqlite3.connect("todo.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        task_name = request.form.get("task", "").strip()
        priority = request.form.get("priority", "Medium")
        due_date = request.form.get("due_date", "").strip() or None

        if task_name:
            cursor.execute(
                "UPDATE tasks SET task = ?, priority = ?, due_date = ? WHERE id = ?",
                (task_name, priority, due_date, task_id)
            )
            conn.commit()

        conn.close()
        return redirect(url_for("home"))

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        return redirect(url_for("home"))

    return render_template("edit.html", task=task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)