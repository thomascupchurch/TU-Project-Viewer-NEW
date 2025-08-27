
# --- Imports ---
import csv
import os
import io
import json
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for server
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory, send_file, flash, make_response

# --- App Setup ---
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'
tasks = []

# --- Calendar export (iCalendar .ics) ---
@app.route('/calendar_export')
def calendar_export():
    def to_ics_datetime(dt):
        return dt.strftime('%Y%m%dT%H%M%S')
    ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TU Project Planner//EN'
    ]
    for t in tasks:
        try:
            start = datetime.strptime(t.get('start', ''), '%Y-%m-%d')
            duration = int(t.get('duration', 1) or 1)
            end = start + timedelta(days=duration)
            summary = t.get('name', 'Task')
            description = t.get('notes', '')
            ics.extend([
                'BEGIN:VEVENT',
                f'SUMMARY:{summary}',
                f'DTSTART:{to_ics_datetime(start)}',
                f'DTEND:{to_ics_datetime(end)}',
                f'DESCRIPTION:{description}',
                'END:VEVENT'
            ])
        except Exception:
            continue
    ics.append('END:VCALENDAR')
    ics_str = '\r\n'.join(ics)
    return Response(ics_str, mimetype='text/calendar', headers={
        'Content-Disposition': 'attachment; filename=project.ics'
    })

# --- Critical Path Calculation ---
def compute_critical_path(tasks):
    # Build task dict by name
    task_dict = {t['name']: t for t in tasks}
    # Build adjacency and reverse adjacency (for dependencies)
    adj = {t['name']: [] for t in tasks}
    rev_adj = {t['name']: [] for t in tasks}
    for t in tasks:
        dep = t.get('depends_on')
        if dep and dep in adj:
            adj[dep].append(t['name'])
            rev_adj[t['name']].append(dep)
    # Topological sort
    visited = set()
    order = []
    def dfs(u):
        visited.add(u)
        for v in adj[u]:
            if v not in visited:
                dfs(v)
        order.append(u)
    for t in tasks:
        if t['name'] not in visited:
            dfs(t['name'])
    order = order[::-1]
    # Forward pass: calculate earliest start/finish
    es = {name: 0 for name in task_dict}
    ef = {name: 0 for name in task_dict}
    for name in order:
        dur = int(task_dict[name].get('duration', 1) or 1)
        es[name] = max([ef[dep] for dep in rev_adj[name]] or [0])
        ef[name] = es[name] + dur
    # Backward pass: calculate latest start/finish
    max_ef = max(ef.values() or [0])
    lf = {name: max_ef for name in task_dict}
    ls = {name: max_ef for name in task_dict}
    for name in reversed(order):
        dur = int(task_dict[name].get('duration', 1) or 1)
        if adj[name]:
            lf[name] = min([ls[succ] for succ in adj[name]])
        ls[name] = lf[name] - dur
    # Critical path: tasks where es==ls
    critical = set(name for name in task_dict if es[name] == ls[name])
    return critical

def parse_tasks_for_gantt(tasks):
    # Flatten tasks into a sorted list with indentation for sub-tasks
    def collect(task, all_tasks, depth):
        try:
            start = datetime.strptime(task['start'], '%Y-%m-%d')
            duration = int(task['duration'])
        except Exception:
            return
        is_milestone = bool(task.get('milestone'))
        all_tasks.append({'name': ('    ' * depth) + task['name'], 'start': start, 'duration': duration, 'is_milestone': is_milestone})
        # Find children
        children = [t for t in tasks if t.get('parent') == task['name']]
        for child in children:
            collect(child, all_tasks, depth+1)
    # Find top-level tasks
    top_level = [t for t in tasks if not t.get('parent')]
    all_tasks = []
    for t in top_level:
        collect(t, all_tasks, 0)
    return all_tasks

@app.route('/gantt.png')
def gantt_chart():
    parsed = parse_tasks_for_gantt(tasks)
    critical = compute_critical_path(tasks)
    fig, ax = plt.subplots(figsize=(8, 4))
    if not parsed:
        ax.text(0.5, 0.5, 'No tasks to display', ha='center', va='center', fontsize=16, color='gray', transform=ax.transAxes)
        ax.set_xlabel('Date')
        fig.tight_layout()
    else:
        names = [t['name'] for t in parsed]
        starts = [mdates.date2num(t['start']) for t in parsed]
        durations = [t['duration'] for t in parsed]
        y_pos = list(range(len(parsed)))
        for i, t in enumerate(parsed):
            if t.get('is_milestone'):
                ax.scatter(starts[i] + durations[i], i, marker='D', s=120, color='#FF8200', edgecolor='black', zorder=5, label='Milestone' if i == 0 else "")
            else:
                # Find the original task to get percent_complete
                task_name = t['name'].lstrip()
                orig_task = next((task for task in tasks if task['name'] == task_name), None)
                try:
                    percent = float(orig_task.get('percent_complete', 0)) if orig_task else 0
                except Exception:
                    percent = 0
                percent = max(0, min(percent, 100))
                dur = t['duration']
                done_dur = dur * percent / 100.0
                # Draw completed (orange) part
                if done_dur > 0:
                    ax.barh(i, done_dur, left=starts[i], height=0.4, align='center', color='#FF8200', edgecolor='black')
                # Draw remaining (gray) part
                if done_dur < dur:
                    ax.barh(i, dur - done_dur, left=starts[i] + done_dur, height=0.4, align='center', color='#555555', edgecolor='black')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel('Date')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        ax.invert_yaxis()
        # Draw parent-child arrows
        name_to_info = {t['name'].lstrip(): (i, starts[i], durations[i]) for i, t in enumerate(parsed)}
        for t in tasks:
            parent = t.get('parent')
            if parent:
                child_name = t['name']
                for i, pt in enumerate(parsed):
                    if pt['name'].lstrip() == child_name:
                        child_idx = i
                        break
                else:
                    continue
                for j, pt in enumerate(parsed):
                    if pt['name'].lstrip() == parent:
                        parent_idx = j
                        break
                else:
                    continue
                parent_y = parent_idx
                child_y = child_idx
                parent_end = starts[parent_idx] + durations[parent_idx]
                child_start = starts[child_idx]
                ax.annotate('', xy=(child_start, child_y), xytext=(parent_end, parent_y),
                            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5, shrinkA=5, shrinkB=5))
        fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

@app.route('/gantt_export/<fmt>')
def gantt_export(fmt):
    parsed = parse_tasks_for_gantt(tasks)
    fig, ax = plt.subplots(figsize=(8, 4))
    if not parsed:
        ax.text(0.5, 0.5, 'No tasks to display', ha='center', va='center', fontsize=16, color='gray', transform=ax.transAxes)
        ax.set_xlabel('Date')
        fig.tight_layout()
    else:
        names = [t['name'] for t in parsed]
        starts = [mdates.date2num(t['start']) for t in parsed]
        durations = [t['duration'] for t in parsed]
        y_pos = list(range(len(parsed)))
        for i, t in enumerate(parsed):
            ax.barh(i, t['duration'], left=starts[i], height=0.4, align='center', color='#FF8200', edgecolor='black')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel('Date')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        ax.invert_yaxis()
        # Draw parent-child arrows
        name_to_info = {t['name'].lstrip(): (i, starts[i], durations[i]) for i, t in enumerate(parsed)}
        for tsk in tasks:
            parent = tsk.get('parent')
            if parent:
                child_name = tsk['name']
                for i, pt in enumerate(parsed):
                    if pt['name'].lstrip() == child_name:
                        child_idx = i
                        break
                else:
                    continue
                for j, pt in enumerate(parsed):
                    if pt['name'].lstrip() == parent:
                        parent_idx = j
                        break
                else:
                    continue
                parent_y = parent_idx
                child_y = child_idx
                parent_end = starts[parent_idx] + durations[parent_idx]
                child_start = starts[child_idx]
                ax.annotate('', xy=(child_start, child_y), xytext=(parent_end, parent_y),
                            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5, shrinkA=5, shrinkB=5))
        fig.tight_layout()
    buf = io.BytesIO()
    if fmt == 'pdf':
        plt.savefig(buf, format='pdf')
        plt.close(fig)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name='project_timeline.pdf', mimetype='application/pdf')
    else:
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name='project_timeline.png', mimetype='image/png')

@app.route('/download_csv')
def download_csv():
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=['name', 'responsible', 'start', 'duration', 'depends_on', 'resources', 'notes', 'pdf_page', 'parent'])
    writer.writeheader()
    for t in tasks:
        row = {k: t.get(k, '') for k in ['name', 'responsible', 'start', 'duration', 'depends_on', 'resources', 'notes', 'pdf_page', 'parent']}
        writer.writerow(row)
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = 'attachment; filename=project.csv'
    output.headers['Content-type'] = 'text/csv'
    return output

@app.route('/', methods=['GET', 'POST'])
def index():
    global tasks
    pdf_uploaded = os.path.exists(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
    parent_options = [('', 'None')] + [(t['name'], t['name']) for t in tasks]
    if request.method == 'POST':
        if 'pdf' in request.files:
            pdf = request.files['pdf']
            if pdf and pdf.filename.lower().endswith('.pdf'):
                pdf.save(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
            return redirect(url_for('index'))
        if 'project_upload' in request.files:
            f = request.files['project_upload']
            if f and f.filename.lower().endswith('.json'):
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        tasks.clear()
                        # Ensure all fields exist for each task
                        for t in data:
                            for k in ['name','responsible','start','duration','depends_on','resources','notes','pdf_page','parent']:
                                t.setdefault(k, '')
                        tasks.extend(data)
                        flash('Project loaded!')
                except Exception:
                    flash('Invalid project file.')
            return redirect(url_for('index'))
        # Add new task from form
        name = request.form.get('name', '').strip()
        responsible = request.form.get('responsible', '').strip()
        start = request.form.get('start', '').strip()
        duration = request.form.get('duration', '').strip()
        depends_on = request.form.get('depends_on', '').strip()
        resources = request.form.get('resources', '').strip()
        notes = request.form.get('notes', '').strip()
        pdf_page = request.form.get('pdf_page', '').strip()
        percent_complete = request.form.get('percent_complete', '0').strip()
        # Handle multiple file uploads for task attachments
        attachment_filenames = []
        if 'attachment' in request.files:
            files = request.files.getlist('attachment')
            for attachment in files:
                if attachment and attachment.filename:
                    safe_name = attachment.filename.replace('..', '').replace('/', '_').replace('\\', '_')
                    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
                    attachment.save(save_path)
                    attachment_filenames.append(safe_name)
        # Handle multiple document links (comma or newline separated)
        document_links = request.form.get('document_link', '').strip()
        links_list = [l.strip() for l in document_links.replace('\r', '').replace('\n', ',').split(',') if l.strip()]
        # Automatically set status based on percent_complete
        try:
            percent_val = float(percent_complete)
        except Exception:
            percent_val = 0
        if percent_val >= 100:
            status = 'Completed'
        elif percent_val > 0:
            status = 'In Progress'
        else:
            status = 'Not Started'
        relation_type = request.form.get('relation_type', 'parent')
        parent = request.form.get('parent', '').strip() if relation_type == 'parent' else ''
        milestone = request.form.get('milestone', '').strip() if relation_type == 'milestone' else ''
        # If depends_on is set, automatically set start date to the day after the dependency ends
        auto_start = start
        if depends_on:
            dep_task = next((t for t in tasks if t['name'] == depends_on), None)
            if dep_task:
                try:
                    dep_start = datetime.strptime(dep_task['start'], '%Y-%m-%d')
                    dep_duration = int(dep_task['duration'])
                    dep_end = dep_start + timedelta(days=dep_duration)
                    auto_start = dep_end.strftime('%Y-%m-%d')
                except Exception:
                    pass
        edit_idx = request.form.get('edit_idx', '').strip()
        if name and duration and auto_start:
            new_task = {
                'name': name,
                'responsible': responsible,
                'start': auto_start,
                'duration': duration,
                'depends_on': depends_on,
                'resources': resources,
                'notes': notes,
                'pdf_page': pdf_page,
                'status': status,
                'percent_complete': percent_complete,
                'parent': parent,
                'milestone': milestone,
                'attachments': attachment_filenames,
                'document_links': links_list
            }
            # Fix: If editing, update the correct task by name (not just index), to avoid issues if table order changes
            if edit_idx.isdigit() and int(edit_idx) < len(tasks):
                # Try to match by name if possible
                old_task = tasks[int(edit_idx)]
                # If the name changed, update all children to point to the new name as parent
                old_name = old_task.get('name')
                if old_name and old_name != name:
                    for t in tasks:
                        if t.get('parent') == old_name:
                            t['parent'] = name
                tasks[int(edit_idx)] = new_task
            else:
                tasks.append(new_task)
        return redirect(url_for('index'))
    return render_template('index.html', tasks=tasks, pdf_uploaded=pdf_uploaded, parent_options=parent_options)

@app.route('/download_project')
def download_project():
    buf = io.BytesIO()
    buf.write(json.dumps(tasks, indent=2).encode('utf-8'))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='project.json', mimetype='application/json')

@app.route('/pdf')
def serve_pdf():
    return send_from_directory(UPLOAD_FOLDER, PDF_FILENAME)

if __name__ == '__main__':
    app.run(debug=True)