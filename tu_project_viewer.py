
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QLabel, QSplitter, QInputDialog, QDateEdit, QSpinBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap
import fitz  # PyMuPDF

# Stub for GanttChartWidget to fix NameError. Replace with actual implementation as needed.
class GanttChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.figure, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def plot_gantt(self, tasks):
        self.ax.clear()
        if not tasks:
            self.canvas.draw()
            return
        # Sort tasks by start date
        tasks_sorted = sorted(tasks, key=lambda t: t['start'])
        names = [t['name'] for t in tasks_sorted]
        starts = [mdates.date2num(t['start']) for t in tasks_sorted]
        durations = [t['duration'] for t in tasks_sorted]
        y_pos = range(len(tasks_sorted))
        # Use the specified color for all bars
        bar_color = '#FF8200'
        self.ax.barh(y_pos, durations, left=starts, height=0.4, align='center', color=bar_color, edgecolor='black')
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels(names)
        self.ax.set_xlabel('Date')
        self.ax.set_title('Gantt Chart')
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.figure.autofmt_xdate()
        # Draw dependencies as arrows
        name_to_idx = {t['name']: i for i, t in enumerate(tasks_sorted)}
        for i, t in enumerate(tasks_sorted):
            dep = t.get('depends_on', '')
            if dep and dep in name_to_idx:
                dep_idx = name_to_idx[dep]
                dep_task = tasks_sorted[dep_idx]
                dep_end = mdates.date2num(dep_task['start'] + timedelta(days=dep_task['duration']))
                # Draw arrow from end of dependency to start of this task
                self.ax.annotate('', xy=(starts[i], i), xytext=(dep_end, dep_idx),
                                 arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
        self.ax.grid(True, axis='x', linestyle='--', alpha=0.6)
        self.canvas.draw()

    def export_chart(self, parent):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(parent, 'Export Gantt Chart', '', 'PNG Files (*.png);;PDF Files (*.pdf)')
        if not path:
            return
        try:
            self.figure.savefig(path, bbox_inches='tight')
            QMessageBox.information(parent, 'Success', f'Gantt chart exported to {path}')
        except Exception as e:
            QMessageBox.critical(parent, 'Error', f'Failed to export chart: {e}')


class PDFViewer(QWidget):
    def load_pdf(self, path):
        try:
            import fitz  # PyMuPDF
            self.doc = fitz.open(path)
            self.page_count = self.doc.page_count
            self.page_num = 0
            self.pdf_path = path
            self.show_page()
            self.update_nav()
        except Exception as e:
            self.label.setText(f"Failed to load PDF: {e}")

    def show_page(self):
        if not hasattr(self, 'doc') or not self.doc:
            return
        try:
            page = self.doc.load_page(self.page_num)
            pix = page.get_pixmap()
            from PyQt5.QtGui import QImage, QPixmap
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            self.label.setText(f"Failed to render page: {e}")

    def update_nav(self):
        if not hasattr(self, 'doc') or not self.doc:
            self.page_label.setText('')
            self.jump_input.setMaximum(1)
            return
        self.page_label.setText(f"Page {self.page_num+1} / {self.page_count}")
        self.jump_input.setMaximum(self.page_count)
        self.jump_input.setValue(self.page_num+1)
    def jump_to_page(self):
        # Stub method to avoid AttributeError. Implement actual logic if needed.
        pass
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel('No PDF loaded')
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton('Previous')
        self.next_btn = QPushButton('Next')
        self.page_label = QLabel('')
        self.jump_input = QSpinBox()
        self.jump_input.setMinimum(1)
        self.jump_input.setMaximum(1)
        self.jump_input.setPrefix('Go to: ')
        self.jump_input.setFixedWidth(100)
        self.jump_input.valueChanged.connect(self.jump_to_page)

# ...existing code...

# Move ProjectViewer to top-level scope
class ProjectViewer(QMainWindow):
    """Main application window for TU Project Viewer."""

    TASK_COLS = ["Task", "Start Date", "Duration (days)", "PDF Page", "Depends On"]
    CONFIG_PATH = 'last_project_path.txt'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('TU Project Viewer')
        self.resize(1200, 800)
        self.setup_ui()

    def open_context_menu(self, position):
        # Placeholder for context menu logic (can be implemented later)
        pass

    def setup_ui(self):
        # Main splitter
        self.splitter = QSplitter()
        self.setCentralWidget(self.splitter)

        # --- Left Panel: PDF Viewer & Project Controls ---
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMinimumWidth(350)

        # Section: PDF Viewer
        pdf_section = QVBoxLayout()
        pdf_label = QLabel('PDF Viewer')
        pdf_label.setStyleSheet('font-weight: bold; font-size: 14px; margin-bottom: 4px;')
        pdf_section.addWidget(pdf_label)
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.setMinimumHeight(250)
        pdf_section.addWidget(self.pdf_viewer)
        self.load_pdf_btn = QPushButton('Load PDF')
        self.load_pdf_btn.setToolTip('Open a PDF file to view and associate with tasks')
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        pdf_section.addWidget(self.load_pdf_btn)
        left_layout.addLayout(pdf_section)

        # Section: Project Controls
        controls_section = QHBoxLayout()
        self.save_btn = QPushButton('💾 Save Project')
        self.save_btn.setToolTip('Save the current project to a file')
        self.save_btn.clicked.connect(self.save_project)
        self.load_btn = QPushButton('📂 Load Project')
        self.load_btn.setToolTip('Load a project from a file')
        self.load_btn.clicked.connect(self.load_project)
        controls_section.addWidget(self.save_btn)
        controls_section.addWidget(self.load_btn)
        left_layout.addLayout(controls_section)

        left_layout.addStretch(1)
        self.splitter.addWidget(left_panel)

        # --- Right Panel: Project Plan & Gantt Chart ---
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        right_panel.setMinimumWidth(600)

        # Section: Project Plan
        plan_label = QLabel('Project Plan')
        plan_label.setStyleSheet('font-weight: bold; font-size: 14px; margin-bottom: 4px;')
        right_layout.addWidget(plan_label)
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(self.TASK_COLS)
        self.task_tree.itemDoubleClicked.connect(self.edit_task)
        self.task_tree.itemClicked.connect(self.on_task_clicked)
        self.task_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.open_context_menu)
        self.task_tree.setMinimumHeight(200)
        right_layout.addWidget(self.task_tree)
        self.add_task_btn = QPushButton('➕ Add Task')
        self.add_task_btn.setToolTip('Add a new task or sub-task to the project plan')
        self.add_task_btn.setFixedWidth(120)
        self.add_task_btn.clicked.connect(self.add_task)
        right_layout.addWidget(self.add_task_btn)

        # Section: Gantt Chart
        gantt_label = QLabel('Gantt Chart')
        gantt_label.setStyleSheet('font-weight: bold; font-size: 14px; margin-top: 12px; margin-bottom: 4px;')
        right_layout.addWidget(gantt_label)
        self.gantt_chart = GanttChartWidget()
        self.gantt_chart.setMinimumHeight(220)
        self.gantt_chart.setStyleSheet('background: #f8f8f8; border: 1px solid #ccc;')
        right_layout.addWidget(self.gantt_chart)

        # Section: Export Buttons
        export_section = QHBoxLayout()
        self.export_gantt_btn = QPushButton('Export Gantt Chart')
        self.export_gantt_btn.setToolTip('Export the Gantt chart as PNG or PDF')
        self.export_gantt_btn.clicked.connect(lambda: self.gantt_chart.export_chart(self))
        self.export_csv_btn = QPushButton('Export Project as CSV')
        self.export_csv_btn.setToolTip('Export all project details to a CSV file')
        self.export_csv_btn.clicked.connect(self.export_project_csv)
        export_section.addWidget(self.export_gantt_btn)
        export_section.addWidget(self.export_csv_btn)
        right_layout.addLayout(export_section)

        right_layout.addStretch(1)
        self.splitter.addWidget(right_panel)

    def load_project(self, path=None):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Load Project', '', 'Project Files (*.json)')
        if not path:
            return
        import json
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.clear_tree()
            pdf_path = data.get('pdf_path', '')
            if pdf_path:
                self.pdf_viewer.load_pdf(pdf_path)
                self.pdf_viewer.pdf_path = pdf_path
            self.deserialize_tree(data.get('tasks', []), self.task_tree)
            self.update_gantt_chart()
            self.save_last_project_path(path)
            QMessageBox.information(self, 'Success', 'Project loaded successfully!')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {e}')

    def export_project_csv(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        import csv
        path, _ = QFileDialog.getSaveFileName(self, 'Export Project as CSV', '', 'CSV File (*.csv)')
        if not path:
            return
        # Gather all tasks and sub-tasks recursively
        rows = []
        def collect_rows(item, parent_name=""):
            row = {
                'Task': item.text(0),
                'Start Date': item.text(1),
                'Duration (days)': item.text(2),
                'PDF Page': item.text(3) if item.columnCount() > 3 else "",
                'Depends On': item.text(4) if item.columnCount() > 4 else "",
                'Parent Task': parent_name
            }
            rows.append(row)
            for i in range(item.childCount()):
                collect_rows(item.child(i), parent_name=item.text(0))
        for i in range(self.task_tree.topLevelItemCount()):
            collect_rows(self.task_tree.topLevelItem(i))
        fieldnames = ['Task', 'Start Date', 'Duration (days)', 'PDF Page', 'Depends On', 'Parent Task']
        try:
            with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            QMessageBox.information(self, 'Success', f'Project exported to {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export project: {e}')

    def save_last_project_path(self, path):
        try:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(path)
        except Exception:
            pass

    def load_last_project_path(self):
        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return None

    def save_project(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(self, 'Save Project', '', 'Project Files (*.json)')
        if not path:
            return
        data = {
            'pdf_path': getattr(self.pdf_viewer, 'pdf_path', ''),
            'tasks': self.serialize_tree()
        }
        import json
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.save_last_project_path(path)
            QMessageBox.information(self, 'Success', 'Project saved successfully!')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {e}')

    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open PDF', '', 'PDF Files (*.pdf)')
        if path:
            self.pdf_viewer.load_pdf(path)

    def add_task(self):
        name, ok = QInputDialog.getText(self, 'Add Task', 'Task name:')
        if not (ok and name):
            return
        # Start date
        date_dialog = QDateEdit()
        date_dialog.setCalendarPopup(True)
        date_dialog.setDate(QDate.currentDate())
        date_ok = QInputDialog.getMultiLineText(self, 'Add Task', 'Enter start date (YYYY-MM-DD):', date_dialog.date().toString("yyyy-MM-dd"))
        if date_ok[1] and date_ok[0]:
            start_date = date_ok[0]
        else:
            return
        # Duration
        duration, ok = QInputDialog.getInt(self, 'Add Task', 'Duration (days):', 1, 1, 365)
        if not ok:
            return
        # PDF Page
        pdf_page, ok = QInputDialog.getInt(self, 'Add Task', 'Associated PDF page (leave 0 for none):', 0, 0, 9999)
        if not ok:
            return
        # Dependencies
        dep_names = self.get_all_task_names()
        dep_names = [n for n in dep_names if n != name]
        depends_on = ""
        if dep_names:
            dep_str, ok = QInputDialog.getItem(self, 'Task Dependency', 'Depends on (optional):', ["None"] + dep_names, 0, False)
            if ok and dep_str and dep_str != "None":
                depends_on = dep_str
        values = [name, start_date, str(duration), str(pdf_page) if pdf_page > 0 else "", depends_on]
        selected = self.task_tree.selectedItems()
        # Only add as a child if the selected item is a top-level item (no parent)
        if selected and selected[0].parent() is None:
            parent = selected[0]
            item = QTreeWidgetItem(values)
            parent.addChild(item)
            parent.setExpanded(True)
        else:
            item = QTreeWidgetItem(values)
            self.task_tree.addTopLevelItem(item)
        self.update_gantt_chart()

    def edit_task(self, item, column):
        old_name = item.text(0)
        old_date = item.text(1)
        old_duration = item.text(2)
        old_page = item.text(3) if item.columnCount() > 3 else ""
        old_dep = item.text(4) if item.columnCount() > 4 else ""
        name, ok = QInputDialog.getText(self, 'Edit Task', 'Task name:', text=old_name)
        if not (ok and name):
            return
        date_ok = QInputDialog.getMultiLineText(self, 'Edit Task', 'Enter start date (YYYY-MM-DD):', old_date)
        if date_ok[1] and date_ok[0]:
            start_date = date_ok[0]
        else:
            return
        duration, ok = QInputDialog.getInt(self, 'Edit Task', 'Duration (days):', int(old_duration) if old_duration.isdigit() else 1, 1, 365)
        if not ok:
            return
        pdf_page, ok = QInputDialog.getInt(self, 'Edit Task', 'Associated PDF page (leave 0 for none):', int(old_page) if old_page.isdigit() else 0, 0, 9999)
        if not ok:
            return
        dep_names = self.get_all_task_names()
        dep_names = [n for n in dep_names if n != name]
        depends_on = old_dep
        if dep_names:
            dep_str, ok = QInputDialog.getItem(self, 'Task Dependency', 'Depends on (optional):', ["None"] + dep_names, dep_names.index(old_dep) + 1 if old_dep in dep_names else 0, False)
            if ok and dep_str and dep_str != "None":
                depends_on = dep_str
            elif ok and dep_str == "None":
                depends_on = ""
        item.setText(0, name)
        item.setText(1, start_date)
        item.setText(2, str(duration))
        item.setText(3, str(pdf_page) if pdf_page > 0 else "")
        item.setText(4, depends_on)
        self.update_gantt_chart()

    def on_task_clicked(self, item, column):
        # If the task has an associated PDF page, jump to it
        page_str = item.text(3) if item.columnCount() > 3 else ""
        if page_str and page_str.isdigit():
            page_num = int(page_str)
            if hasattr(self.pdf_viewer, 'doc') and self.pdf_viewer.doc and 1 <= page_num <= self.pdf_viewer.page_count:
                self.pdf_viewer.page_num = page_num - 1
                self.pdf_viewer.show_page()
                self.pdf_viewer.update_nav()

    def update_gantt_chart(self):
        # Gather all tasks and sub-tasks recursively, including dependencies
        def collect_tasks(item, tasks):
            for i in range(item.childCount()):
                collect_tasks(item.child(i), tasks)
            name = item.text(0)
            start = item.text(1)
            duration = item.text(2)
            depends_on = item.text(4) if item.columnCount() > 4 else ""
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                dur = int(duration)
                tasks.append({
                    'name': name,
                    'start': start_dt,
                    'duration': dur,
                    'depends_on': depends_on,
                    'original_start': start_dt
                })
            except Exception:
                pass
        all_tasks = []
        for i in range(self.task_tree.topLevelItemCount()):
            collect_tasks(self.task_tree.topLevelItem(i), all_tasks)

        # Adjust start dates based on dependencies
        name_to_task = {t['name']: t for t in all_tasks}
        changed = True
        # Repeat until no more changes (handles chains of dependencies)
        while changed:
            changed = False
            for t in all_tasks:
                dep = t.get('depends_on', '')
                if dep and dep in name_to_task:
                    dep_task = name_to_task[dep]
                    dep_end = dep_task['start'] + timedelta(days=dep_task['duration'])
                    if t['start'] < dep_end:
                        t['start'] = dep_end
                        changed = True
        self.gantt_chart.plot_gantt(all_tasks)

    def serialize_tree(self):
        def serialize_item(item):
            d = {
                'values': [item.text(i) for i in range(item.columnCount())],
                'children': [serialize_item(item.child(i)) for i in range(item.childCount())]
            }
            return d
        return [serialize_item(self.task_tree.topLevelItem(i)) for i in range(self.task_tree.topLevelItemCount())]

    def deserialize_tree(self, data, parent):
        from PyQt5.QtWidgets import QTreeWidgetItem
        for entry in data:
            values = entry['values']
            if len(values) < len(self.TASK_COLS):
                values += [""] * (len(self.TASK_COLS) - len(values))
            item = QTreeWidgetItem(values)
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)
            self.deserialize_tree(entry.get('children', []), item)

    def clear_tree(self):
        self.task_tree.clear()

    def get_all_task_names(self):
        names = []
        def collect_names(item):
            names.append(item.text(0))
            for i in range(item.childCount()):
                collect_names(item.child(i))
        for i in range(self.task_tree.topLevelItemCount()):
            collect_names(self.task_tree.topLevelItem(i))
        return names


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ProjectViewer()
    last_path = viewer.load_last_project_path()
    if last_path:
        viewer.load_project(last_path)
    viewer.show()
    sys.exit(app.exec_())
