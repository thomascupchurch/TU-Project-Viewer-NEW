# --- Project Timeline Helper ---
def get_project_timeline_data(tasks):
    # Extract milestones and phases (tasks with 'milestone' or status 'Completed' or 'In Progress')
    timeline_items = []
    for t in tasks:
        # Treat as milestone if 'milestone' field is set or if marked as milestone in type
        if t.get('milestone') or t.get('status') == 'Completed' or t.get('status') == 'In Progress':
            timeline_items.append({
                'name': t.get('milestone') or t.get('name'),
                'date': t.get('start'),
                'type': 'milestone' if t.get('milestone') else 'phase',
            })
    # Sort by date
    timeline_items = [item for item in timeline_items if item['date']]
    timeline_items.sort(key=lambda x: x['date'])
    return timeline_items
@app.route('/timeline')
def timeline_page():
    load_tasks()
    timeline_items = get_project_timeline_data(tasks)
    return render_template('timeline.html', tasks=tasks, timeline_items=timeline_items)
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
from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory, send_file, flash, make_response, jsonify
import zipfile

app = Flask(__name__)

# --- Calendar View Route ---
@app.route('/calendar')
def calendar_view():
    return render_template('calendar.html')

# --- Kanban View Route ---
@app.route('/kanban')
def kanban_view():
    return render_template('kanban.html', tasks=tasks)


# --- Tasks JSON for Calendar & API ---
@app.route('/tasks_json')
def tasks_json():
    # Return all fields for each task, including id and parent (by id)
    return jsonify(tasks)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PDF_FILENAME = 'uploaded.pdf'

TASKS_FILE = os.path.join(os.path.dirname(__file__), 'tasks.json')
tasks = []
next_task_id = 1

# --- Delete Task ---
@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json
    idx = data.get('task_idx')
    if idx is None:
        return jsonify({'success': False, 'error': 'Missing task index'}), 400
    try:
        idx = int(idx)
        if idx < 0 or idx >= len(tasks):
            return jsonify({'success': False, 'error': 'Invalid task index'}), 400
        # Remove attachments from disk
        for fname in tasks[idx].get('attachments', []):
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
                 # --- Calendar View Route ---
        tasks.pop(idx)
        save_tasks()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



# --- Persistent Storage Helpers ---
def load_tasks():
    global tasks, next_task_id
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    tasks.clear()
                    max_id = 0
                    for idx, t in enumerate(data):
                        for k, default in [
                            ('name', ''),
                            ('responsible', ''),
                            ('start', ''),
                            ('duration', ''),
                            ('depends_on', ''),
                            ('resources', ''),
                            ('notes', ''),
                            ('pdf_page', ''),
                            ('parent', None),
                            ('status', 'Not Started'),
                            ('percent_complete', '0'),
                            ('milestone', ''),
                            ('attachments', []),
                            ('document_links', []),
                        ]:
                            if k not in t:
                                t[k] = default
                        # Assign unique id if missing
                        if 'id' not in t:
                            t['id'] = idx + 1
                        max_id = max(max_id, t['id'])
                        # Coerce attachments and document_links to lists if needed
                        if not isinstance(t.get('attachments', []), list):
                            if isinstance(t['attachments'], str) and t['attachments'].strip() == '':
                                t['attachments'] = []
                            elif isinstance(t['attachments'], str):
                                t['attachments'] = [t['attachments']]
                            else:
                                t['attachments'] = list(t['attachments']) if t['attachments'] else []
                        if not isinstance(t.get('document_links', []), list):
                            if isinstance(t['document_links'], str) and t['document_links'].strip() == '':
                                t['document_links'] = []
                            elif isinstance(t['document_links'], str):
                                t['document_links'] = [t['document_links']]
                            else:
                                t['document_links'] = list(t['document_links']) if t['document_links'] else []
                    # Update parent field to use id, not name
                    name_to_id = {t['name']: t['id'] for t in data}
                    for t in data:
                        if t.get('parent') and t['parent'] in name_to_id:
                            t['parent'] = name_to_id[t['parent']]
                    tasks.extend(data)
                    next_task_id = max_id + 1
        except Exception:
            pass

def save_tasks():
    try:
        print(f"[DEBUG] save_tasks() called. Saving {len(tasks)} tasks to {TASKS_FILE}")
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        print(f"[DEBUG] save_tasks() wrote file successfully.")
    except Exception as e:
        print(f"[DEBUG] save_tasks() failed: {e}")

# --- Delete Attachment from Task ---
@app.route('/delete_attachment', methods=['POST'])
def delete_attachment():
    data = request.json
    task_idx = data.get('task_idx')
    filename = data.get('filename')
    if task_idx is None or filename is None:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    try:
        task_idx = int(task_idx)
        task = tasks[task_idx]
        if 'attachments' in task and filename in task['attachments']:
            task['attachments'].remove(filename)
            # Remove file from disk if it exists
            fpath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(fpath):
                os.remove(fpath)
            save_tasks()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Attachment not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Calendar export (iCalendar .ics) ---
@app.route('/calendar_export')
def calendar_export():
    def to_ics_datetime(dt):
        return dt.strftime('%Y%m%dT%H%M%S')
# --- Project Export as ZIP (JSON + Attachments) ---
import zipfile

@app.route('/download_project_zip')
def download_project_zip():
    # Prepare in-memory zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add project.json
        project_json = json.dumps(tasks, indent=2).encode('utf-8')
        zf.writestr('project.json', project_json)
        # Add all unique attachments referenced in tasks
        added = set()
        for t in tasks:
            for fname in t.get('attachments', []):
                if fname and fname not in added:
                    fpath = os.path.join(UPLOAD_FOLDER, fname)
                    if os.path.exists(fpath):
                        zf.write(fpath, arcname=os.path.join('attachments', fname))
                        added.add(fname)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='project_bundle.zip', mimetype='application/zip')
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

@app.route('/gantt')
def gantt_page():
    load_tasks()
    return render_template('gantt.html', tasks=tasks)

@app.route('/gantt.png')
def gantt_chart():
    print("[DEBUG] Entered gantt_chart route")
    try:
        print("[DEBUG] Tasks before rendering Gantt chart:", json.dumps(tasks, indent=2, ensure_ascii=False))
        parsed = parse_tasks_for_gantt(tasks)
        critical = compute_critical_path(tasks)
        fig, ax = plt.subplots(figsize=(24, 12))
        plt.rcParams.update({'font.size': 20})
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
    except Exception as e:
        print("[ERROR] Exception in gantt_chart:", str(e))
        import traceback
        traceback.print_exc()
        return Response('Error rendering Gantt chart', mimetype='text/plain')

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
    load_tasks()
    pdf_uploaded = os.path.exists(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
    parent_options = [('', 'None')] + [(t['name'], t['name']) for t in tasks]
    if request.method == 'POST':
        print("[DEBUG] POST request received at index route.")
        print(f"[DEBUG] request.files: {request.files}")
        print(f"[DEBUG] request.form: {request.form}")
        if 'pdf' in request.files:
            print("[DEBUG] Entered PDF upload branch.")
            pdf = request.files['pdf']
            if pdf and pdf.filename.lower().endswith('.pdf'):
                pdf.save(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
            return redirect(url_for('index'))
        if 'project_upload' in request.files:
            print("[DEBUG] Entered project_upload branch.")
            f = request.files['project_upload']
            if request.method == 'POST':
                if 'pdf' in request.files:
                    print("[DEBUG] Entered nested PDF upload branch.")
                    pdf = request.files['pdf']
                    if pdf and pdf.filename.lower().endswith('.pdf'):
                        pdf.save(os.path.join(UPLOAD_FOLDER, PDF_FILENAME))
                    return redirect(url_for('index'))
                if 'project_upload' in request.files:
                    print("[DEBUG] Entered nested project_upload branch.")
                    f = request.files['project_upload']
                    if f and f.filename.lower().endswith('.json'):
                        try:
                            data = json.load(f)
                            if isinstance(data, list):
                                tasks.clear()
                                for t in data:
                                    for k, default in [
                                        ('name', ''),
                                        ('responsible', ''),
                                        ('start', ''),
                                        ('duration', ''),
                                        ('depends_on', ''),
                                        ('resources', ''),
                                        ('notes', ''),
                                        ('pdf_page', ''),
                                        ('parent', ''),
                                        ('status', 'Not Started'),
                                        ('percent_complete', '0'),
                                        ('milestone', ''),
                                        ('attachments', []),
                                        ('document_links', []),
                                    ]:
                                        if k not in t:
                                            t[k] = default
                                    if not isinstance(t.get('attachments', []), list):
                                        if isinstance(t['attachments'], str) and t['attachments'].strip() == '':
                                            t['attachments'] = []
                                        elif isinstance(t['attachments'], str):
                                            t['attachments'] = [t['attachments']]
                                        else:
                                            t['attachments'] = list(t['attachments']) if t['attachments'] else []
                                    if not isinstance(t.get('document_links', []), list):
                                        if isinstance(t['document_links'], str) and t['document_links'].strip() == '':
                                            t['document_links'] = []
                                        elif isinstance(t['document_links'], str):
                                            t['document_links'] = [t['document_links']]
                                        else:
                                            t['document_links'] = list(t['document_links']) if t['document_links'] else []
                                tasks.extend(data)
                                save_tasks()
                                flash('Project loaded!')
                                load_tasks()
                        except Exception:
                            flash('Invalid project file.')
                    return redirect(url_for('index'))
                # Add new task from form
        print("[DEBUG] Entered new task creation branch.")
        name = request.form.get('name', '').strip()
        responsible = request.form.get('responsible', '').strip()
        start = request.form.get('start', '').strip()
        duration = request.form.get('duration', '').strip()
        depends_on = request.form.get('depends_on', '').strip()
        resources = request.form.get('resources', '').strip()
        notes = request.form.get('notes', '').strip()
        pdf_page = request.form.get('pdf_page', '').strip()
        percent_complete = request.form.get('percent_complete', '0').strip()
        color = request.form.get('color', '#4287f5').strip()
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
            if attachment_filenames:
                print(f"[DEBUG] Saved attachments for task '{name}': {attachment_filenames}")
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
        parent_name = request.form.get('parent', '').strip() if relation_type == 'parent' else None
        milestone = request.form.get('milestone', '').strip() if relation_type == 'milestone' else ''
        # Find parent id if parent_name is set
        parent_id = None
        if parent_name:
            for t in tasks:
                if t['name'] == parent_name:
                    parent_id = t['id']
                    break
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
        changed = False
        if name and duration and auto_start:
            global next_task_id
            # If editing, merge new attachments with existing ones
            if edit_idx.isdigit() and int(edit_idx) < len(tasks):
                old_task = tasks[int(edit_idx)]
                merged_attachments = list(old_task.get('attachments', []))
                for fname in attachment_filenames:
                    if fname not in merged_attachments:
                        merged_attachments.append(fname)
                # If the name changed, update all children to point to the new id as parent
                old_id = old_task.get('id')
                if old_id:
                    for t in tasks:
                        if t.get('parent') == old_id:
                            t['parent'] = old_id
                new_task = {
                    'id': old_task['id'],
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
                    'parent': parent_id,
                    'milestone': milestone,
                    'attachments': merged_attachments,
                    'document_links': links_list,
                    'color': color
                }
                tasks[int(edit_idx)] = new_task
                changed = True
            else:
                 # New task: always set attachments field (even if empty)
                new_task = {
                    'id': next_task_id,
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
                    'parent': parent_id,
                    'milestone': milestone,
                    'attachments': attachment_filenames,
                    'document_links': links_list,
                    'color': color
                }
                tasks.append(new_task)
                next_task_id += 1
                changed = True
        print(f"[DEBUG] changed={changed}, name='{name}', duration='{duration}', auto_start='{auto_start}'")
        if changed:
            print("[DEBUG] New task form submitted.")
            print(f"[DEBUG] Form data: {request.form}")
            print(f"[DEBUG] New task: {new_task}")
            print(f"[DEBUG] Task list before save: {tasks}")
            save_tasks()
        return redirect(url_for('index'))
    return render_template('index.html', tasks=tasks, pdf_uploaded=pdf_uploaded, parent_options=parent_options)
    # ...existing code...
# --- Update Task Status (AJAX for Kanban drag-and-drop) ---
@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    data = request.get_json()
    print('[DEBUG] /update_task_status called with:', data)
    try:
        task_id = int(data.get('id', -1))
    except Exception as e:
        print('[DEBUG] Invalid task id:', data.get('id'))
        return jsonify({'success': False, 'error': 'Invalid task id'})
    new_status = data.get('status')
    found = False
    for t in tasks:
        print(f"[DEBUG] Checking task id {t['id']} against {task_id}")
        if t['id'] == task_id:
            t['status'] = new_status
            # Automatically update percent_complete for certain statuses
            if new_status == 'Completed':
                t['percent_complete'] = 100
            elif new_status == 'Not Started':
                t['percent_complete'] = 0
            save_tasks()
            print(f"[DEBUG] Updated task {task_id} to status {new_status} and percent_complete {t.get('percent_complete')}")
            found = True
            return jsonify({'success': True})
    if not found:
        print(f"[DEBUG] Task id {task_id} not found in tasks: {[t['id'] for t in tasks]}")
    return jsonify({'success': False, 'error': 'Task not found'})

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
    load_tasks()
    app.run(debug=True)