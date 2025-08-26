
from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory, send_file, flash, make_response
import csv
import os
import io
import json

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'

# In-memory task list (replace with file/db for production)
tasks = []

# ...existing code...

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
        import matplotlib.dates as mdates
        starts = [mdates.date2num(t['start']) for t in parsed]
        durations = [t['duration'] for t in parsed]
        y_pos = list(range(len(parsed)))
        ax.barh(y_pos, durations, left=starts, height=0.4, align='center', color='#FF8200', edgecolor='black')
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


from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory, send_file, flash, make_response
import csv
import os
import io
import json

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'

# In-memory task list (replace with file/db for production)
tasks = []

@app.route('/download_csv')
def download_csv():
    si = io.StringIO()
    writer = csv.DictWriter(si, fieldnames=['name', 'start', 'duration', 'depends_on', 'resources', 'notes', 'parent'])
    writer.writeheader()
    for t in tasks:
        row = {k: t.get(k, '') for k in ['name', 'start', 'duration', 'depends_on', 'resources', 'notes', 'parent']}
        writer.writerow(row)
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = 'attachment; filename=project.csv'
    output.headers['Content-type'] = 'text/csv'
    return output


app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'

# In-memory task list (replace with file/db for production)
tasks = []

import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for server
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
def parse_tasks_for_gantt(tasks):
    # Flatten tasks into a sorted list with indentation for sub-tasks
    def collect(task, all_tasks, depth):
        try:
            start = datetime.strptime(task['start'], '%Y-%m-%d')
            duration = int(task['duration'])
        except Exception:
            return
        all_tasks.append({'name': ('    ' * depth) + task['name'], 'start': start, 'duration': duration})
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

        # --- Critical Path Calculation ---
        # Build a task graph: name -> {duration, depends_on, children}
        task_map = {t['name']: {'duration': int(t['duration']), 'depends_on': t.get('depends_on', '').strip(), 'children': []} for t in tasks}
        for t in tasks:
            dep = t.get('depends_on', '').strip()
            if dep and dep in task_map:
                task_map[dep]['children'].append(t['name'])

        # Find all end tasks (no children)
        end_tasks = [name for name, v in task_map.items() if not v['children']]

        # For each end task, walk back to build all paths, keep the longest
        def walk_path(name, path, total):
            dep = task_map[name]['depends_on']
            if dep and dep in task_map:
                return walk_path(dep, [name] + path, total + task_map[dep]['duration'])
            else:
                return [name] + path, total
        critical_path = []
        max_duration = -1
        for end in end_tasks:
            path, dur = walk_path(end, [], task_map[end]['duration'])
            if dur > max_duration:
                max_duration = dur
                critical_path = path

        # Draw all bars in University of Tennessee orange (#FF8200)
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
    import io
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

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
                            for k in ['name','start','duration','depends_on','resources','notes','parent']:
                                t.setdefault(k, '')
                        tasks.extend(data)
                        flash('Project loaded!')
                except Exception:
                    flash('Invalid project file.')
            return redirect(url_for('index'))
        # Add new task from form
        name = request.form.get('name', '').strip()
        start = request.form.get('start', '').strip()
        duration = request.form.get('duration', '').strip()
        depends_on = request.form.get('depends_on', '').strip()
        resources = request.form.get('resources', '').strip()
        notes = request.form.get('notes', '').strip()
        pdf_page = request.form.get('pdf_page', '').strip()
        parent = request.form.get('parent', '').strip()
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
        if name and duration and auto_start:
            tasks.append({
                'name': name,
                'start': auto_start,
                'duration': duration,
                'depends_on': depends_on,
                'resources': resources,
                'notes': notes,
                'pdf_page': pdf_page,
                'parent': parent
            })
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
